"""Build every hartwell task's environment bundle from the four-month world log.

    uv run python datasets/hartwell/build_tasks.py [world_log] [--refresh-truth]

Bundles are materialized seatless: no ``--user`` seat is passed, so the
Gmail server projects the whole firm's mail org-wide rather than a single
mailbox — the tasks are matter-hygiene work that reads across seats, and
the storyline audits in build_history.py ran against the same seatless
projection. Each bundle keeps the tool databases offstage under
``state/`` and gives the agent only ``workspace/``. Bundles are derived
data and stay local.

A task that declares ``[[environment.mcp_servers]]`` has been converted to
Harbor's schema, so its bundle is also staged into ``environment/`` — the
one directory Harbor uploads for a prebuilt-image task. Before staging, the
task's stdout oracle is run against the fresh bundle and compared byte-for-byte
with ``tests/oracle.json``. Only ``--refresh-truth`` updates that artifact.
See harbor_stage.py.
"""

import argparse
import hashlib
import json
import math
import os
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from workbench.environment import materialize

sys.path.insert(0, str(Path(__file__).parent))

from harbor_stage import stage  # noqa: E402

TASKS = Path(__file__).parent / "tasks"
ORACLE_TIMEOUT_SECONDS = 300


class OracleError(RuntimeError):
    """The task oracle did not produce a safe deterministic deliverable."""


class OracleDriftError(OracleError):
    """The fresh bundle's oracle differs from the committed certification."""


class EvidenceContract(BaseModel):
    """Machine-checkable scope of the retained evidence workpaper."""

    model_config = ConfigDict(extra="forbid")

    primary_field: str = Field(min_length=1)
    records: int = Field(ge=1)
    item_fields: tuple[str, ...] = ()
    items: int | None = Field(default=None, ge=1)
    source_surfaces: tuple[Literal["gmail", "slack", "imanage", "clio"], ...]


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Materialize, certify, and stage every Hartwell task."
    )
    argument_parser.add_argument(
        "world_log",
        nargs="?",
        type=Path,
        default=Path("out/hartwell/world.jsonl"),
    )
    argument_parser.add_argument(
        "--refresh-truth",
        action="store_true",
        help="replace committed oracle artifacts from freshly materialized bundles",
    )
    return argument_parser


def hash_tree(root: Path) -> str:
    """Hash names, types, modes, links, and bytes without following symlinks."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        metadata = path.lstat()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(stat.S_IFMT(metadata.st_mode).to_bytes(4, "big"))
        digest.update(stat.S_IMODE(metadata.st_mode).to_bytes(4, "big"))
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(os.readlink(path).encode())
        elif stat.S_ISREG(metadata.st_mode):
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
    return digest.hexdigest()


def _finite_json(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_json(item) for key, item in value.items()
        )
    return value is None or isinstance(value, bool | int | str)


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _canonical_json(document: dict[str, object]) -> bytes:
    return (
        json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def run_oracle(task: Path, bundle: Path) -> bytes:
    """Run a task's stdout oracle against a fresh bundle without side effects."""
    workspace = bundle / "workspace"
    before = hash_tree(workspace)
    environment = os.environ.copy()
    environment["WORKBENCH_STATE"] = str((bundle / "state").resolve())
    try:
        completed = subprocess.run(
            [sys.executable, str((task / "solution" / "solve.py").resolve())],
            cwd=workspace,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=ORACLE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise OracleError(f"{task.name} oracle failed: {error}") from error
    after = hash_tree(workspace)
    if after != before:
        raise OracleError(f"{task.name} oracle modified the agent workspace")
    try:
        loaded = json.loads(completed.stdout, parse_constant=_invalid_constant)
        if not isinstance(loaded, dict) or not _finite_json(loaded):
            raise ValueError("not a finite JSON object")
        return _canonical_json(loaded)
    except (RecursionError, TypeError, ValueError) as error:
        raise OracleError(
            f"{task.name} oracle must emit one valid finite JSON object"
        ) from error


def certify_evidence_contract(task: Path, oracle: bytes) -> None:
    """Prove the fresh oracle still spans the declared evidence population."""
    try:
        config = tomllib.loads((task / "task.toml").read_text())
        raw_contract = config.get("metadata", {}).get("evidence")
        if raw_contract is None:
            raise OracleError(f"{task.name} evidence contract is missing")
        contract = EvidenceContract.model_validate(raw_contract)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise OracleError(
            f"{task.name} evidence contract is invalid: {error}"
        ) from error
    if len(set(contract.source_surfaces)) < 2:
        raise OracleError(
            f"{task.name} evidence contract needs at least two source surfaces"
        )
    try:
        document = json.loads(oracle)
    except (RecursionError, TypeError, ValueError) as error:
        raise OracleError(f"{task.name} oracle is not valid JSON") from error
    records = document.get(contract.primary_field)
    if not isinstance(records, list) or len(records) != contract.records:
        actual = len(records) if isinstance(records, list) else "non-list"
        raise OracleError(
            f"{task.name} evidence contract expected {contract.records} records "
            f"in {contract.primary_field}, found {actual}"
        )
    if contract.items is None:
        if contract.item_fields:
            raise OracleError(
                f"{task.name} evidence contract declares item_fields without items"
            )
        return
    if not contract.item_fields:
        raise OracleError(
            f"{task.name} evidence contract declares items without item_fields"
        )
    nested_items = 0
    for record in records:
        if not isinstance(record, dict):
            raise OracleError(f"{task.name} evidence contract expected object records")
        for field in contract.item_fields:
            values = record.get(field)
            if not isinstance(values, list):
                raise OracleError(
                    f"{task.name} evidence contract expected list field {field}"
                )
            nested_items += len(values)
    if nested_items != contract.items:
        raise OracleError(
            f"{task.name} evidence contract expected {contract.items} nested "
            f"evidence items, found {nested_items}"
        )


def certify_oracle(task: Path, bundle: Path, *, refresh: bool) -> Path:
    """Refresh explicitly or prove fresh output equals committed oracle bytes."""
    actual = run_oracle(task, bundle)
    certify_evidence_contract(task, actual)
    artifact = task / "tests" / "oracle.json"
    if refresh:
        temporary = artifact.with_name(f".{artifact.name}.tmp")
        temporary.write_bytes(actual)
        temporary.replace(artifact)
        return artifact
    if not artifact.exists():
        raise OracleDriftError(
            f"{task.name} oracle artifact is missing: {artifact}; "
            "review the fresh answer, then rerun with --refresh-truth"
        )
    if artifact.read_bytes() != actual:
        raise OracleDriftError(
            f"{task.name} fresh oracle does not match {artifact}; "
            "review the drift, then rerun with --refresh-truth"
        )
    return artifact


def _is_harbor_task(task: Path) -> bool:
    config = tomllib.loads((task / "task.toml").read_text())
    return bool(config.get("environment", {}).get("mcp_servers"))


def build_task(world_log: Path, task: Path, *, refresh: bool) -> None:
    result = materialize(world_log, task / "bundle")
    print(f"{task.name}: {result.event_count} events -> {result.bundle}")
    artifact = certify_oracle(task, result.bundle, refresh=refresh)
    action = "refreshed" if refresh else "certified"
    print(f"{task.name}: oracle {action} -> {artifact}")
    if _is_harbor_task(task):
        stage_dir = stage(result.bundle, task / "environment")
        print(f"{task.name}: staged -> {stage_dir.parent}")


def main() -> int:
    arguments = parser().parse_args()
    world_log = arguments.world_log
    if not world_log.exists():
        raise SystemExit(
            f"{world_log} not found — build the four-month history first: "
            "uv run python datasets/hartwell/build_history.py --days all"
        )
    for task in sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists()):
        build_task(world_log, task, refresh=arguments.refresh_truth)
    return 0


if __name__ == "__main__":
    sys.exit(main())

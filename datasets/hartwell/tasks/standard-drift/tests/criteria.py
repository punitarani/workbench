"""Safe criteria for the standard-drift Reward Kit dimensions."""

import json
import math
import os
import re
import stat
from collections import Counter
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 1_000_000
PUBLIC_FIELDS = frozenset(
    {"playbook_path", "ndas", "silent_versions", "term", "residuals"}
)
CLAUSE_FIELDS = frozenset(
    {"playbook_standard", "practice", "document_path", "version", "date"}
)


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not isinstance(
        document.get("playbook_path"), str
    ):
        return False
    ndas = document.get("ndas")
    if not isinstance(ndas, dict) or not all(
        isinstance(path, str) and status in {"conforms", "deviates"}
        for path, status in ndas.items()
    ):
        return False
    silent = document.get("silent_versions")
    if not isinstance(silent, list) or not all(
        isinstance(item, str) for item in silent
    ):
        return False
    for key in ("term", "residuals"):
        clause = document.get(key)
        if not isinstance(clause, dict) or set(clause) != CLAUSE_FIELDS:
            return False
        if not all(
            isinstance(clause.get(field), str)
            for field in ("playbook_standard", "practice", "document_path", "date")
        ) or not _integer(clause.get("version")):
            return False
    return True


def _submitted(workspace: Path, path: str) -> dict[str, object]:
    descriptor = -1
    try:
        descriptor = os.open(workspace / path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_DELIVERABLE_BYTES
        ):
            return {}
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            contents = stream.read(MAX_DELIVERABLE_BYTES + 1)
        if len(contents) > MAX_DELIVERABLE_BYTES:
            return {}
        loaded = json.loads(contents.decode())
    except ValueError, UnicodeDecodeError, OSError:
        return {}
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return (
        loaded
        if isinstance(loaded, dict) and _finite_json(loaded) and _valid_contract(loaded)
        else {}
    )


def _version(value: object) -> str:
    text = str(value).strip().upper()
    return text if text.startswith("LEGAL!") else f"LEGAL!{text}"


def _counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(_version(value) for value in values)


def _f1(got: Counter[str], want: Counter[str]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision = hits / sum(got.values())
    recall = hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(description="{key} exactly equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="{key}.{field} contains a certified marker", shared=True)
def clause_marker(
    workspace: Path, path: str, key: str, field: str, markers: list[str]
) -> bool:
    clause = _submitted(workspace, path).get(key)
    if not isinstance(clause, dict):
        return False
    value = str(clause.get(field, "")).lower()
    return any(marker.lower() in value for marker in markers)


@criterion(description="{key}.{field} exactly equals the certified value", shared=True)
def clause_equals(
    workspace: Path, path: str, key: str, field: str, expected: object
) -> bool:
    clause = _submitted(workspace, path).get(key)
    return isinstance(clause, dict) and clause.get(field) == expected


def _nda_counter(values: object) -> Counter[str]:
    if not isinstance(values, dict):
        return Counter()
    return Counter(
        f"{str(path).strip()}\0{str(status).strip().lower()}"
        for path, status in values.items()
    )


@criterion(description="NDA certification F1", shared=True)
def nda_f1(workspace: Path, path: str, expected: dict[str, str]) -> float:
    return _f1(
        _nda_counter(_submitted(workspace, path).get("ndas")), _nda_counter(expected)
    )


@criterion(description="NDA certification exact", shared=True)
def nda_exact(workspace: Path, path: str, expected: dict[str, str]) -> bool:
    return _nda_counter(_submitted(workspace, path).get("ndas")) == _nda_counter(
        expected
    )


@criterion(description="silent version F1", shared=True)
def version_f1(workspace: Path, path: str, key: str, expected: list[str]) -> float:
    return _f1(_counter(_submitted(workspace, path).get(key)), _counter(expected))


@criterion(description="silent versions exact", shared=True)
def version_exact(workspace: Path, path: str, key: str, expected: list[str]) -> bool:
    return _counter(_submitted(workspace, path).get(key)) == _counter(expected)


@criterion(description="exact public schema and types", shared=True)
def exact_schema(workspace: Path, path: str) -> bool:
    return bool(_submitted(workspace, path))


@criterion(description="agent invoked {tool}", shared=True)
def tool_invoked(
    workspace: Path, tool: str, path: str = "/logs/agent/trajectory.json"
) -> bool:
    del workspace
    try:
        data = json.loads(Path(path).read_text())
    except ValueError, UnicodeDecodeError, OSError:
        return False
    expression = re.compile(rf"\btools\.(?:[A-Za-z_]\w*__)*{re.escape(tool)}\s*\(")
    for step in data.get("steps", []) if isinstance(data, dict) else []:
        for call in step.get("tool_calls", []) if isinstance(step, dict) else []:
            if not isinstance(call, dict):
                continue
            name = str(call.get("function_name", ""))
            if name == tool or name.endswith(f"__{tool}"):
                return True
            arguments = call.get("arguments", {})
            text = arguments if isinstance(arguments, str) else json.dumps(arguments)
            if expression.search(text):
                return True
    return False

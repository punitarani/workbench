"""Build the Calder task environment from the epoch world log.

    uv run python datasets/calder/build_task.py [world_log]

Materializes the h1-billing-audit bundle seatless (org-wide Gmail — the audit
reads across seats), verifies the reference solution reproduces the committed
oracle byte-for-byte, and stages the Harbor ``environment/`` directory via the
shared harbor_stage machinery. Bundles are derived data and stay local.
"""

import json
import subprocess
import sys
from pathlib import Path

from environment.materialize import materialize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hartwell"))

from harbor_stage import stage  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
TASK = Path(__file__).resolve().parent / "tasks" / "h1-billing-audit"
DEFAULT_LOG = REPO / "out" / "calder" / "epoch-6mo" / "world.jsonl"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    world_log = Path(args[0]) if args else DEFAULT_LOG
    bundle = TASK / "bundle"

    env = materialize(world_log, bundle, seat=None)
    print(f"materialized {env.event_count} events -> {bundle}")

    produced = bundle / "workspace" / "h1_billing_audit.json"
    subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py"), str(produced)],
        check=True,
        env={"WORKBENCH_STATE": str(bundle / "state"), "PATH": "/usr/bin:/bin"},
    )
    oracle = json.loads((TASK / "tests" / "oracle.json").read_text())
    answer = json.loads(produced.read_text())
    produced.unlink()
    if answer != oracle:
        raise SystemExit("reference solution no longer reproduces tests/oracle.json")
    print("oracle verified against the reference solution")

    staged = stage(bundle, TASK / "environment", repo_root=REPO)
    print(f"staged harbor environment -> {staged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

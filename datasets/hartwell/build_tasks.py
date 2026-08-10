"""Build every hartwell task's environment bundle from the four-month world log.

    uv run python datasets/hartwell/build_tasks.py [world_log]

Bundles are materialized seatless: no ``--user`` seat is passed, so the
Gmail server projects the whole firm's mail org-wide rather than a single
mailbox — the tasks are matter-hygiene work that reads across seats, and
the storyline audits in build_history.py ran against the same seatless
projection. Each bundle keeps the tool databases offstage under
``state/`` and gives the agent only ``workspace/``. Bundles are derived
data and stay local.

A task that declares ``[[environment.mcp_servers]]`` has been converted to
Harbor's schema, so its bundle is also staged into ``environment/`` — the
one directory Harbor uploads for a prebuilt-image task. See harbor_stage.py.
"""

import sys
import tomllib
from pathlib import Path

from workbench.environment import materialize

sys.path.insert(0, str(Path(__file__).parent))

from harbor_stage import stage  # noqa: E402

TASKS = Path(__file__).parent / "tasks"


def _is_harbor_task(task: Path) -> bool:
    config = tomllib.loads((task / "task.toml").read_text())
    return bool(config.get("environment", {}).get("mcp_servers"))


def main() -> int:
    world_log = Path(sys.argv[1] if len(sys.argv) > 1 else "out/hartwell/world.jsonl")
    if not world_log.exists():
        raise SystemExit(
            f"{world_log} not found — build the four-month history first: "
            "uv run python datasets/hartwell/build_history.py --days all"
        )
    for task in sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists()):
        result = materialize(world_log, task / "bundle")
        print(f"{task.name}: {result.event_count} events -> {result.bundle}")
        if _is_harbor_task(task):
            stage_dir = stage(result.bundle, task / "environment")
            print(f"{task.name}: staged -> {stage_dir.parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

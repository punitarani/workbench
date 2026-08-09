"""Build every hartwell task workspace from the four-month world log.

    uv run python datasets/hartwell/build_tasks.py [world_log]

Workspaces are materialized seatless: no ``--user`` seat is passed, so the
Gmail server projects the whole firm's mail org-wide rather than a single
mailbox — the tasks are matter-hygiene work that reads across seats, and
the storyline audits in build_history.py ran against the same seatless
projection. Workspaces are derived data and stay local.
"""

import sys
from pathlib import Path

from workbench.environment import materialize

TASKS = Path(__file__).parent / "tasks"


def main() -> int:
    world_log = Path(sys.argv[1] if len(sys.argv) > 1 else "out/hartwell/world.jsonl")
    if not world_log.exists():
        raise SystemExit(
            f"{world_log} not found — build the four-month history first: "
            "uv run python datasets/hartwell/build_history.py --days all"
        )
    for task in sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists()):
        result = materialize(world_log, task / "workspace")
        print(f"{task.name}: {result.event_count} events -> {result.workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

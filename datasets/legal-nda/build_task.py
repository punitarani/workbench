"""Build every legal-nda task's environment bundle from the recorded legal day.

    uv run python datasets/legal-nda/build_task.py [world_log]

Each task gets a ``bundle/`` holding the offstage tool databases and the
agent's own ``workspace/``. Bundles are derived data and stay local; this
builder is the committed, reproducible path from a recorded day to the
task fixtures.
"""

import sys
from pathlib import Path

from environment import materialize

TASKS = Path(__file__).parent / "tasks"


def main() -> int:
    world_log = Path(sys.argv[1] if len(sys.argv) > 1 else "out/legal-day/world.jsonl")
    if not world_log.exists():
        raise SystemExit(
            f"{world_log} not found — replay the demo day first (see docs/WORKBENCH.md)"
        )
    for task in sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists()):
        result = materialize(world_log, task / "bundle")
        print(f"{task.name}: {result.event_count} events -> {result.bundle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

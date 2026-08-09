"""Build the vantage-triage task workspace from the recorded legal day.

    uv run python datasets/legal-nda/build_task.py [world_log]

The workspace is derived data and stays local; this builder is the
committed, reproducible path from a recorded day to the task fixture.
"""

import sys
from pathlib import Path

from workbench.environment import materialize

TASK = Path(__file__).parent / "tasks" / "vantage-triage"


def main() -> int:
    world_log = Path(sys.argv[1] if len(sys.argv) > 1 else "out/legal-day/world.jsonl")
    if not world_log.exists():
        raise SystemExit(
            f"{world_log} not found — replay the demo day first "
            "(see docs/simulation-engine.md)"
        )
    result = materialize(world_log, TASK / "workspace")
    print(f"workspace built: {result.event_count} events -> {result.workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

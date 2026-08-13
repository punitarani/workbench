"""Serve one tool system over stdio.

    python -m workbench.tools.serve gmail --db state/gmail.db --user per-...

``--user`` sets the seat: person-scoped systems (a Gmail mailbox, Clio's
who_am_i) read it via WORKBENCH_SEAT. In the container this runs behind
run-as-environment so the database is readable only by the environment
user; the MCP surface is the sole aperture.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from workbench.tools import compliance, framework
from workbench.tools.registry import REGISTRY, build_server

# ``compliance`` is the one write system and is deliberately NOT in the global
# REGISTRY (that drives project_all, coherence, and every read-only task's
# surface). It is served opt-in, per task, from a database created and seeded at
# build time rather than projected from the world log.
_OPT_IN = {"compliance": compliance.SYSTEM}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tool",
        choices=sorted({system.name for system in REGISTRY} | set(_OPT_IN)),
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--user", default=None, help="seat person id")
    args = parser.parse_args(argv)

    if args.user:
        os.environ["WORKBENCH_SEAT"] = args.user
    if args.tool in _OPT_IN:
        server = framework.build_server(_OPT_IN[args.tool], args.db)
    else:
        server = build_server(args.tool, args.db)
    asyncio.run(server.run_stdio_async())
    return 0


if __name__ == "__main__":
    sys.exit(main())

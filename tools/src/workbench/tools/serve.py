"""Serve one tool system over stdio.

    python -m workbench.tools.serve mail --db state/mail.db

In the container this runs behind run-as-environment so the database is
readable only by the environment user; the MCP surface is the sole aperture.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from workbench.tools import PROJECTORS
from workbench.tools.server import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=sorted(PROJECTORS))
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args(argv)

    server = build_server(args.tool, args.db)
    asyncio.run(server.run_stdio_async())
    return 0


if __name__ == "__main__":
    sys.exit(main())

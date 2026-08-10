#!/bin/sh
# Harbor's oracle uploads this directory to /solution and runs it as the
# agent user. The reference solution reads the tool databases directly, and
# they are offstage — /home/environment/state is 0700, environment-owned — so
# the oracle goes through run-as-environment, the same setuid helper the MCP
# servers use. The oracle therefore exercises the real boundary rather than a
# copy of the data.
#
# Outside a container (the task's pytest, working from an unpacked bundle)
# there is no helper and no boundary to cross, so the script runs directly.
set -eu

SOLVE="$(cd "$(dirname "$0")" && pwd)/solve.py"

if command -v run-as-environment >/dev/null 2>&1; then
    exec run-as-environment python3 "$SOLVE"
fi

exec python3 "$SOLVE"

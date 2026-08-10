#!/bin/sh
# Harbor's oracle uploads this directory to /solution and runs it as the
# agent user. The reference solution reads the environment-owned databases
# through one allowlisted executable that can only run /solution/solve.py.
# Its JSON returns on stdout; this agent-owned shell redirects it into an
# agent-created temporary file and atomically installs the deliverable.
#
# Outside a container (the task's pytest, working from an unpacked bundle)
# there is no helper and no boundary to cross, so the script runs directly.
set -eu

SOLVE="$(cd "$(dirname "$0")" && pwd)/solve.py"
TEMP=$(mktemp .dispute.json.XXXXXX)
trap 'rm -f "$TEMP"' EXIT HUP INT TERM

if [ -x /usr/local/bin/run-as-environment ]; then
    /usr/local/bin/run-as-environment /usr/local/libexec/workbench/oracle > "$TEMP"
else
    python3 "$SOLVE" > "$TEMP"
fi

mv -f "$TEMP" dispute.json
trap - EXIT HUP INT TERM

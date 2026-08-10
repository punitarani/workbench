#!/bin/sh
# Harbor mounts this directory at /solution. The approved restricted oracle
# runs only /solution/solve.py as the environment user and returns JSON on
# stdout; this agent-owned wrapper installs that output atomically.
set -eu

SOLVE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)/solve.py"
TEMP=$(mktemp .visitor-log.json.XXXXXX)
trap 'rm -f "$TEMP"' EXIT HUP INT TERM

if [ -x /usr/local/bin/run-as-environment ]; then
    /usr/local/bin/run-as-environment /usr/local/libexec/workbench/oracle > "$TEMP"
else
    python3 "$SOLVE" > "$TEMP"
fi

mv -f "$TEMP" visitor-log.json
trap - EXIT HUP INT TERM

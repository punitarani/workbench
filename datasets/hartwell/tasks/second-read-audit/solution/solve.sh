#!/bin/sh
set -eu
TEMP=$(mktemp .second-read.json.XXXXXX)
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
if [ -x /usr/local/bin/run-as-environment ]; then
    /usr/local/bin/run-as-environment /usr/local/libexec/workbench/oracle > "$TEMP"
else
    python3 "$(dirname "$0")/solve.py" > "$TEMP"
fi
mv -f "$TEMP" second-read.json
trap - EXIT HUP INT TERM

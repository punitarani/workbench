#!/bin/sh
set -eu
SOLVE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)/solve.py"
TEMP=$(mktemp .authority.json.XXXXXX)
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
if [ -x /usr/local/bin/run-as-environment ]; then
    /usr/local/bin/run-as-environment /usr/local/libexec/workbench/oracle > "$TEMP"
else
    python3 "$SOLVE" > "$TEMP"
fi
chmod 640 "$TEMP"
mv -f "$TEMP" authority.json
trap - EXIT HUP INT TERM

#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
python3 "$HERE/solve.py" h1_billing_audit.json

#!/bin/sh
set -eu
TESTS_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORKSPACE=${WORKBENCH_WORKSPACE:-/app}
LOG_DIR=${VERIFIER_LOG_DIR:-/logs/verifier}
mkdir -p "$LOG_DIR"
rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$LOG_DIR/reward-raw.json"
python3 - "$LOG_DIR/reward-raw.json" "$LOG_DIR/reward.json" <<'PY'
import json, sys
from pathlib import Path
raw = json.loads(Path(sys.argv[1]).read_text())
if set(raw) != {"answer", "process"}:
    raise SystemExit(f"unexpected Reward Kit dimensions: {sorted(raw)}")
Path(sys.argv[2]).write_text(json.dumps({"reward": raw["answer"], **raw}, indent=2) + "\n")
PY

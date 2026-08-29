#!/bin/sh
# The verifier entrypoint. Without this file nothing runs Reward Kit at all.
set -eu
TESTS_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORKSPACE=${WORKBENCH_WORKSPACE:-/app}
LOG_DIR=${VERIFIER_LOG_DIR:-/logs/verifier}
mkdir -p "$LOG_DIR"
rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$LOG_DIR/reward-raw.json"

# Keep what the agent actually wrote, beside its score. Without this a trial
# preserves the number and not the answer, and "why did it miss that row" is
# a guess -- which is the one question that may not be guessed when deciding
# whether a sub-1.0 criterion is a model failure or a defect in the task.
#
# Into LOG_DIR rather than /logs/artifacts: both are collected, but the
# verifier user cannot write to the latter.
for deliverable in "$WORKSPACE"/*.json; do
  [ -f "$deliverable" ] || continue
  cp "$deliverable" "$LOG_DIR/submitted-$(basename "$deliverable")"
  echo "kept $(basename "$deliverable")"
done

python3 - "$LOG_DIR/reward-raw.json" "$LOG_DIR/reward.json" <<'PYEOF'
import json, sys
from pathlib import Path

raw = json.loads(Path(sys.argv[1]).read_text())
# An empty dimension set is what a task with no registered criteria produces,
# and it reads downstream as a score of nothing rather than as a failure.
if set(raw) != {"answer", "process"}:
    raise SystemExit(f"unexpected Reward Kit dimensions: {sorted(raw)}")
Path(sys.argv[2]).write_text(
    json.dumps({"reward": raw["answer"], **raw}, indent=2) + "\n"
)
PYEOF

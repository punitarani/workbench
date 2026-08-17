#!/bin/sh
set -eu
TESTS_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORKSPACE=${WORKBENCH_WORKSPACE:-/app}
LOG_DIR=${VERIFIER_LOG_DIR:-/logs/verifier}
mkdir -p "$LOG_DIR"
rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$LOG_DIR/reward-raw.json"
# Keep what the agent actually wrote, beside its score. Without this a trial
# preserves the number and not the answer, and "why did it miss that row"
# is a guess -- which is the one thing that may not decide whether a
# sub-1.0 criterion is a model failure or a defect.
#
# Into LOG_DIR and not /logs/artifacts: that directory is collected too, but
# the verifier user cannot write to it, and the first version of this hid
# that behind `2>/dev/null || true` and reported nothing. LOG_DIR is where
# reward.json already goes, so it is known writable.
for deliverable in "$WORKSPACE"/*.json; do
  [ -f "$deliverable" ] || continue
  cp "$deliverable" "$LOG_DIR/submitted-$(basename "$deliverable")"
  echo "kept $(basename "$deliverable")"
done
python3 - "$LOG_DIR/reward-raw.json" "$LOG_DIR/reward.json" <<'PYEOF'
import json, sys
from pathlib import Path
raw = json.loads(Path(sys.argv[1]).read_text())
if set(raw) != {"answer", "process"}:
    raise SystemExit(f"unexpected Reward Kit dimensions: {sorted(raw)}")
Path(sys.argv[2]).write_text(json.dumps({"reward": raw["answer"], **raw}, indent=2) + "\n")
PYEOF

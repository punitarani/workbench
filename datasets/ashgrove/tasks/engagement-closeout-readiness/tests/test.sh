#!/bin/sh
set -eu
TESTS_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORKSPACE=${WORKBENCH_WORKSPACE:-/app}
LOG_DIR=${VERIFIER_LOG_DIR:-/logs/verifier}
mkdir -p "$LOG_DIR"
# Keep what the agent actually wrote. Without this a trial preserves its
# score and not its answer, and "why did it miss that row" becomes a
# guess -- which is exactly the question every sub-1.0 criterion has to
# answer before it can be called a model failure rather than a defect.
ARTIFACTS=${VERIFIER_ARTIFACT_DIR:-/logs/artifacts}
if mkdir -p "$ARTIFACTS" 2>/dev/null; then
  find "$WORKSPACE" -maxdepth 1 -name '*.json' -size -4M \
    -exec cp {} "$ARTIFACTS/" \; 2>/dev/null || true
fi
rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$LOG_DIR/reward-raw.json"
python3 - "$LOG_DIR/reward-raw.json" "$LOG_DIR/reward.json" <<'PYEOF'
import json, sys
from pathlib import Path
raw = json.loads(Path(sys.argv[1]).read_text())
if set(raw) != {"answer", "process"}:
    raise SystemExit(f"unexpected Reward Kit dimensions: {sorted(raw)}")
Path(sys.argv[2]).write_text(json.dumps({"reward": raw["answer"], **raw}, indent=2) + "\n")
PYEOF

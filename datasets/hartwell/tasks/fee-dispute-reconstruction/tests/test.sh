#!/bin/sh
# Harbor's verifier entry point. Reward Kit discovers the dimension
# directories beside this file and writes its raw per-dimension scores first.
# The final Harbor envelope makes answer the canonical reward while retaining
# process as a diagnostic metric and leaves Reward Kit's details untouched.
#
# workbench:dev preinstalls harbor-rewardkit[all] (the image's
# REWARDKIT_VERSION), so the verifier phase needs no egress and no resolve —
# which is what lets task.toml set [verifier] network_mode = "no-network".
# The uvx form is the fallback for an image without it, pinned to the same
# version so the two paths cannot grade differently; it needs egress, so a
# task relying on it must widen [verifier] network_mode.
set -eu

REWARDKIT_VERSION=0.1.7
TESTS_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
WORKSPACE=${WORKBENCH_WORKSPACE:-/app}
LOG_DIR=${VERIFIER_LOG_DIR:-/logs/verifier}
RAW_REWARD="$LOG_DIR/reward-raw.json"
FINAL_REWARD="$LOG_DIR/reward.json"

mkdir -p "$LOG_DIR"

if command -v rewardkit >/dev/null 2>&1; then
    rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$RAW_REWARD"
else
    uvx --from "harbor-rewardkit[all]==${REWARDKIT_VERSION}" \
        rewardkit "$TESTS_DIR" --workspace "$WORKSPACE" --output "$RAW_REWARD"
fi

python3 - "$RAW_REWARD" "$FINAL_REWARD" <<'PY'
import json
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
final_path = Path(sys.argv[2])
raw = json.loads(raw_path.read_text())
if set(raw) != {"answer", "process"}:
    raise SystemExit(f"unexpected Reward Kit dimensions: {sorted(raw)}")
final_path.write_text(
    json.dumps(
        {"reward": raw["answer"], "answer": raw["answer"], "process": raw["process"]},
        indent=2,
    )
    + "\n"
)
PY

#!/usr/bin/env bash
# Keep a long recording alive until it finishes the window it was asked for.
#
# A six-month epoch is tens of thousands of network calls over roughly a
# day of wall time. Over that long, the run does not fail for interesting
# reasons — it fails because a socket dropped, a provider returned a 5xx
# after its retries, or the machine slept. Every day checkpoints, so the
# recovery is always the same: resume.
#
# What this does NOT do is retry forever. A run that dies three times
# without completing a single further day is not having bad luck, it is
# broken, and looping on it turns a loud failure into a quiet one. That
# is the whole reason the engine raises on cassette misses and budget
# exhaustion rather than degrading, and a supervisor that swallowed those
# would undo it.
#
#   scripts/supervise_epoch.sh <dataset> <out-dir> <cassette> <days> [concurrency]
set -uo pipefail

DATASET="${1:?dataset name, e.g. merrick}"
OUT="${2:?output directory}"
CASSETTE="${3:?cassette directory}"
DAYS="${4:?calendar days in the window}"
CONCURRENCY="${5:-48}"

LOG="/tmp/${DATASET}-epoch.log"
RUNNER="datasets/${DATASET}/run_epoch.py"
PY="./.venv/bin/python"

# The runner refuses record mode without OPENROUTER_API_KEY, and calling
# the venv interpreter directly does not load `.env` the way the
# documented `uv run --env-file .env` invocation does. This script drove
# a 180-day run straight into "record mode requires OPENROUTER_API_KEY",
# three times, and then reported it as "not a transient failure" —
# correctly, and uselessly, because the cause was one unset variable.
#
# Sourced with `set -a` so every assignment exports. Values never reach
# stdout: the log this writes is world-readable for as long as it exists.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "[supervise] OPENROUTER_API_KEY is not set and .env did not provide" \
         "it; record mode cannot start." >&2
    exit 1
fi

# The artifact, not the progress log. `telemetry.jsonl` gains a day row
# during the run; `world.jsonl` is written once per segment at the very
# end, and it is the only thing anything downstream reads. A kill between
# the two leaves telemetry claiming a day the world does not contain —
# reproduced: eight telemetry rows, seven days in the world, supervisor
# prints "done" and exits 0.
world_days() {
    local count
    count=$(grep -c '"tag": *"sim.day.ended"' "${OUT}/world.jsonl" 2>/dev/null || true)
    echo "${count:-0}"
}

days_done() {
    # `grep -c` prints 0 *and* exits 1 when nothing matches, so a bare
    # `|| echo 0` fires as well and the function returns "0\n0". Every
    # integer test downstream then errors and evaluates false — including
    # the stall check, which scored a restart that really recorded five
    # days as no progress and spent patience it had earned.
    local count
    count=$(grep -c '"kind": *"day"' "${OUT}/telemetry.jsonl" 2>/dev/null || true)
    echo "${count:-0}"
}

# Weekends are skipped by the day chain, so a window's calendar length is
# not its workday count — and five-sevenths is not either. Counting the
# actual weekdays from the epoch gives 130 for a 180-day window starting
# on a Monday, where `DAYS * 5 / 7` gives 128. The script would have
# announced a complete world two days short, and nothing downstream
# checks span: the build has no day count and the truncated world would
# simply have become the graded one.
target=$(
    "${PY}" - "${DAYS}" <<'EOF'
import sys
from datetime import date, timedelta

# Kept in step with EPOCH_START in the workplace definition.
start = date.fromisoformat("2026-01-05")
days = int(sys.argv[1])
print(sum(1 for i in range(days) if (start + timedelta(days=i)).weekday() < 5))
EOF
)
stalled=0

while :; do
    before=$(days_done)
    if [ "${before}" -ge "${target}" ] && [ "$(world_days)" -ge "${target}" ]; then
        echo "[supervise] $(world_days) workdays in world.jsonl — done"
        exit 0
    fi

    # Branch on whether a run *exists*, not on whether it produced a day.
    # The store is created before the first step and `start` refuses over
    # an existing one, so a crash before the first day-end — the most
    # likely failure, and the one with ten minutes of exposure per
    # attempt — left this issuing `start` three times, being refused
    # twice, and declaring "not a transient failure". Resume, which works,
    # was never tried.
    if [ ! -e "${OUT}/run.db" ]; then
        echo "[supervise] starting ${DATASET} (${DAYS} days, target ${target} workdays)"
        "${PY}" -u "${RUNNER}" start --days "${DAYS}" --mode record \
            --out "${OUT}" --cassette "${CASSETTE}" \
            --concurrency "${CONCURRENCY}" >> "${LOG}" 2>&1
    else
        echo "[supervise] resuming at ${before}/${target} workdays"
        "${PY}" -u "${RUNNER}" resume \
            --out "${OUT}" --cassette "${CASSETTE}" \
            --concurrency "${CONCURRENCY}" >> "${LOG}" 2>&1
    fi
    status=$?

    after=$(days_done)
    if [ "${after}" -ge "${target}" ]; then
        # Accept on the artifact and on a clean exit, never on the
        # progress log alone. `status` was captured and used only in an
        # echo, so a segment that returned non-zero still ended the run.
        exported=$(world_days)
        if [ "${status}" -eq 0 ] && [ "${exported}" -ge "${target}" ]; then
            echo "[supervise] ${exported} workdays in world.jsonl — done"
            exit 0
        fi
        echo "[supervise] telemetry says ${after} but world.jsonl holds" \
             "${exported} and the segment exited ${status}; resuming"
    fi

    # Progress resets patience; no progress spends it. Three dead restarts
    # that advanced nothing is a broken run, not a flaky network.
    if [ "${after}" -gt "${before}" ]; then
        stalled=0
    else
        stalled=$(( stalled + 1 ))
    fi
    if [ "${stalled}" -ge 3 ]; then
        echo "[supervise] three restarts without advancing past day ${after};" \
             "exit ${status}. Not a transient failure — stopping so it is loud." >&2
        tail -40 "${LOG}" >&2
        exit 1
    fi

    echo "[supervise] exited ${status} at day ${after}/${target}; retry ${stalled}/3 in 60s"
    sleep 60
done

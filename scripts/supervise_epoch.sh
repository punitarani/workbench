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

days_done() {
    grep -c '"kind": *"day"' "${OUT}/telemetry.jsonl" 2>/dev/null || echo 0
}

# Weekends are skipped by the day chain, so the window's calendar length
# is not its workday count. Five sevenths, rounded down, is the target.
target=$(( DAYS * 5 / 7 ))
stalled=0

while :; do
    before=$(days_done)
    if [ "${before}" -ge "${target}" ]; then
        echo "[supervise] ${before} workdays recorded, target ${target} — done"
        exit 0
    fi

    if [ "${before}" -eq 0 ]; then
        echo "[supervise] starting ${DATASET} (${DAYS} days)"
        "${PY}" -u "${RUNNER}" start --days "${DAYS}" --mode record \
            --out "${OUT}" --cassette "${CASSETTE}" \
            --concurrency "${CONCURRENCY}" >> "${LOG}" 2>&1
    else
        echo "[supervise] resuming from day ${before}"
        "${PY}" -u "${RUNNER}" resume \
            --out "${OUT}" --cassette "${CASSETTE}" \
            --concurrency "${CONCURRENCY}" >> "${LOG}" 2>&1
    fi
    status=$?

    after=$(days_done)
    if [ "${after}" -ge "${target}" ]; then
        echo "[supervise] ${after} workdays recorded — done"
        exit 0
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

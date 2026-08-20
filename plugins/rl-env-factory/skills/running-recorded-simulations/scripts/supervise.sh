#!/usr/bin/env bash
# Keep a long run alive until it finishes, without resetting it or lying
# about whether it did.
#
#   supervise.sh --start CMD --resume CMD --progress CMD --artifact CMD \
#                --target N [--patience 3] [--pause 60] [--log PATH]
#
# --progress and --artifact are commands that print a number on stdout.
# `progress` is the cheap running count (a telemetry log). `artifact` is the
# durable output anything downstream will actually read. They are separate
# because a kill between the two leaves progress claiming work the artifact
# does not hold, and accepting on progress alone ships a truncated result.
set -uo pipefail

START= RESUME= PROGRESS= ARTIFACT= TARGET= PATIENCE=3 PAUSE=60 LOG=/dev/null
while [ $# -gt 0 ]; do
    case "$1" in
        --start)    START=$2;    shift 2 ;;
        --resume)   RESUME=$2;   shift 2 ;;
        --progress) PROGRESS=$2; shift 2 ;;
        --artifact) ARTIFACT=$2; shift 2 ;;
        --target)   TARGET=$2;   shift 2 ;;
        --patience) PATIENCE=$2; shift 2 ;;
        --pause)    PAUSE=$2;    shift 2 ;;
        --log)      LOG=$2;      shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
for required in START RESUME PROGRESS ARTIFACT TARGET; do
    if [ -z "${!required}" ]; then
        echo "missing --${required,,}" >&2
        exit 2
    fi
done

# A counting command prints 0 *and* exits non-zero when it matches nothing.
# Written as `$(cmd || echo 0)` both fire and the result is "0\n0", which
# makes every integer test below error and evaluate false -- including the
# stall check, so a run that really advanced would be scored as stalled.
count() {
    local out
    out=$(eval "$1" 2>/dev/null | tail -1 | tr -dc '0-9')
    echo "${out:-0}"
}

done_yet() {
    [ "$(count "${PROGRESS}")" -ge "${TARGET}" ] \
        && [ "$(count "${ARTIFACT}")" -ge "${TARGET}" ]
}

if done_yet; then
    echo "[supervise] already at target ($(count "${ARTIFACT}")/${TARGET})"
    exit 0
fi

stalled=0
while :; do
    before=$(count "${PROGRESS}")

    # Branch on whether a run EXISTS, not on whether it has progressed. The
    # store is created before the first checkpoint and `start` refuses to
    # overwrite it, so a crash in the first minutes leaves a store that only
    # `resume` can continue. Branching on progress issues `start`, gets
    # refused, and calls a recoverable run unrecoverable.
    if [ "${before}" -eq 0 ] && ! eval "${RESUME} --dry-run" >/dev/null 2>&1; then
        echo "[supervise] starting (target ${TARGET})"
        eval "${START}" >>"${LOG}" 2>&1
    else
        echo "[supervise] resuming at ${before}/${TARGET}"
        eval "${RESUME}" >>"${LOG}" 2>&1
    fi
    # Captured immediately: a pipe would return the last command's status,
    # which is always zero, and the supervisor would accept a failed run.
    status=$?

    after=$(count "${PROGRESS}")
    if [ "${after}" -ge "${TARGET}" ]; then
        held=$(count "${ARTIFACT}")
        if [ "${status}" -eq 0 ] && [ "${held}" -ge "${TARGET}" ]; then
            echo "[supervise] ${held}/${TARGET} in the artifact -- done"
            exit 0
        fi
        echo "[supervise] progress says ${after} but the artifact holds" \
             "${held} and the run exited ${status}; continuing"
    fi

    # Progress resets patience; no progress spends it. Attempts are not the
    # signal -- a run failing repeatedly while still advancing is a flaky
    # network, and one that advances nothing is broken.
    if [ "${after}" -gt "${before}" ]; then
        stalled=0
    else
        stalled=$(( stalled + 1 ))
    fi

    if [ "${stalled}" -ge "${PATIENCE}" ]; then
        echo "[supervise] ${PATIENCE} attempts without passing ${after};" \
             "exit ${status}. Not transient -- stopping so it is loud." >&2
        tail -40 "${LOG}" >&2 2>/dev/null
        exit 1
    fi

    echo "[supervise] exited ${status} at ${after}/${TARGET};" \
         "retry ${stalled}/${PATIENCE} in ${PAUSE}s"
    sleep "${PAUSE}"
done

#!/bin/sh
# Restart the Merrick six-month recording on the corrected engine.
#
# v2 is unusable: it was recorded on an engine that lost 85% of the firm's
# document authoring and wrote its own pydantic errors into personas'
# memories at importance 10, which the firm then discussed across Slack,
# mail and its time narratives as a platform outage. See the commit
# "engine: the simulation's own failures were being recorded as the firm's
# history".
#
# Concurrency stays at 48 because that is the setting whose throughput is
# measured (~6.2 calendar days per hour; 180 days in roughly 29 hours),
# not because 48 is optimal. The code's own comment argues useful
# concurrency is the cohort width, 21. Tune it when nothing is riding on
# the next 29 hours.
set -eu
cd "$(dirname "$0")/.."

OLD_PID="${1:-}"
if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "epoch $OLD_PID is still running; stop it first:  kill $OLD_PID" >&2
    exit 1
fi

[ -f .env ] && . ./.env
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY (it lives in .env, which is gitignored)}"
export OPENROUTER_API_KEY

OUT="${OUT:-out/merrick/epoch-v4}"
LOG="/tmp/merrick-$(basename "$OUT").log"
if [ -e "$OUT" ]; then
    echo "$OUT already exists; move it aside or pick another --out" >&2
    exit 1
fi

nohup ./.venv/bin/python -u datasets/merrick/run_epoch.py start \
    --days 180 --mode record \
    --out "$OUT" --cassette "cassettes/merrick-$(basename "$OUT")" \
    --concurrency 48 > "$LOG" 2>&1 &

echo "started $(basename "$OUT") as pid $!"
echo "  log        $LOG"
echo "  telemetry  $OUT/telemetry.jsonl   (one JSON line per simulated day)"
echo "  progress   ./.venv/bin/python datasets/merrick/run_epoch.py status --out $OUT"

#!/bin/sh
# Everything a finished recording needs measured, in one command.
#
#     sh scripts/measure_new_corpus.sh out/merrick/epoch-v7
#
# The runbook in docs/fidelity/when-the-corpus-lands.md is 420 lines and
# every step of it that a machine can do is here. What is left over is
# judgement: choosing a window from the numbers this prints, and writing
# the brief. Those are the parts that went wrong when they were done from
# a previous world's figures rather than this one's.
#
# Safe against a running recording: the export reads a WAL snapshot and
# truncates at whatever was committed. Run it early and often — probing a
# partial corpus is what found four task defects that would otherwise have
# shipped.
set -eu
cd "$(dirname "$0")/.."
OUT="${1:?usage: measure_new_corpus.sh <epoch dir>}"
WORK="${WORK:-$(mktemp -d)}"

echo "== 1. recover the world log =================================="
if [ ! -f "$OUT/world.jsonl" ]; then
    ./.venv/bin/python - "$OUT" "$WORK" <<'PY'
import sqlite3, sys, pathlib
src, work = sys.argv[1], sys.argv[2]
d = sqlite3.connect(f"{work}/run.db")
sqlite3.connect(f"file:{src}/run.db?mode=ro", uri=True).backup(d)
d.close()
print(f"   backed up a live store to {work}/run.db")
PY
    ./.venv/bin/python scripts/export_world_log.py --out "$WORK" >/dev/null
    LOG="$WORK/world.jsonl"
else
    LOG="$OUT/world.jsonl"
    echo "   using the finished export at $LOG"
fi

echo "== 2. materialize ==========================================="
./.venv/bin/python - "$LOG" "$WORK" <<'PY'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from environment.materialize import materialize
materialize(Path(sys.argv[1]), Path(sys.argv[2]) / "bundle")
print("   bundle built")
PY
STATE="$WORK/bundle/state"

echo "== 3. does the world still hold together? ===================="
./.venv/bin/python - "$STATE" "$LOG" <<'PY'
import sys, sqlite3, collections, json, re
sys.path.insert(0, "src")
from pathlib import Path
state, log = Path(sys.argv[1]), Path(sys.argv[2])

served = {r[0] for r in sqlite3.connect(
    f"file:{state / 'imanage.db'}?mode=ro", uri=True).execute(
    "SELECT path FROM documents")}
ws = state.parent / "workspace"
disk = {str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()}
ok = len(served & disk)
print(f"   file room     {ok}/{len(served)} served paths resolve "
      f"({100 * ok / max(len(served), 1):.1f}%)   {len(disk)} files")

# The engine's own failures becoming the firm's history. This screen found
# 151 events of it in one recording; a clean world scores zero.
fiction = re.compile(r"to[/-]?cc\b|recipient omission|omitted recipient"
                     r"|no recipient|read.?aloud|cc policy", re.I)
hits = collections.Counter()
total = 0
for line in log.open():
    if '"tag": "sim.' in line or '"tag":"sim.' in line:
        continue
    total += 1
    if fiction.search(line):
        hits[json.loads(line)["tag"]] += 1
verdict = "clean" if not hits else f"CONTAMINATED {dict(hits)}"
print(f"   engine fiction {sum(hits.values())} of {total} on-stage events — {verdict}")
PY

echo "== 4. what each task's own forms find ======================="
WORKBENCH_STATE="$STATE" ./.venv/bin/python datasets/merrick/measure_transcripts.py 2>/dev/null \
    | grep -E "^corpus|VERDICT|supersession|any mention|speaker's own|guessing" || true
echo
echo "   for live-commitment-register, sweep windows with:"
echo "     WORKBENCH_STATE=$STATE ./.venv/bin/python \\"
echo "       datasets/merrick/measure_commitment_window.py --first-day N --last-day M"
echo
echo "   it refuses a window over the word ceiling, under the row floor, or"
echo "   under the supersession floor — and prints every value the brief needs."
echo
echo "== 5. before you build on this world ========================"
./.venv/bin/python - <<'STALE'
import pathlib
stale = [
    path
    for path in sorted(pathlib.Path("datasets/merrick/tasks").glob("*/tests/oracle.json"))
    if not path.with_suffix(".world").exists()
]
if stale:
    print(f"   {len(stale)} oracle(s) on disk carry no world stamp:")
    for path in stale:
        print(f"     {path}")
    print("   The build refuses each with 'derived from an unrecorded world'")
    print("   -- correct, and it reads like a defect. They are probe artifacts")
    print("   of a world that is gone. Delete them, or pass --refresh-truth")
    print("   deliberately and know which of the two you are doing.")
else:
    print("   no unstamped oracles -- the build compares against provenance")
STALE

echo "== 6. what is still owed ===================================="
echo "   Three tasks are retired (double-booked-week, court-clock-computation,"
echo "   one-sentence-two-dates); their briefs carry a STOP banner saying why."
echo "   Five are staged. Each brief's «MEASURE» notes now carry counts from"
echo "   the previous record — RE-COUNT them here rather than carrying them"
echo "   over. That is the mistake this whole file exists to prevent."
echo
echo "   working dir: $WORK"

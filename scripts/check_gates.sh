#!/bin/sh
# Every refusal in the merrick build AND in the engine, broken on purpose.
#
#     sh scripts/check_gates.sh
#
# A gate is code whose whole value is refusing. It is also code that
# usually runs on the happy path and returns quietly, so a gate that has
# stopped refusing looks exactly like a gate with nothing to refuse — and
# every green build afterwards is evidence for nothing.
#
# These are the mutations that were run by hand on 2026-08-23, kept so the
# next person changing a gate can re-run them in one command instead of
# reconstructing what "checked" meant. The first pass found two survivors
# in `_refuse_leaked_rows`, a gate that already had four passing tests:
# nothing exercised the branches that DECLINE to fire, which is where a
# gate turns from a defect-catcher into a nuisance.
#
# Exits non-zero if any mutation survives or any anchor has gone stale.
set -eu
cd "$(dirname "$0")/.."

# This script edits src/simulation/gm/grounded.py, one of the seven files
# whose byte digest keys a resume. Each mutation leaves it changed for about
# a second, and if a live recording dies inside that window its resume
# computes a different fingerprint and refuses to continue -- the safe
# failure, and still an hour of somebody's recording lost to a test run.
#
# The author of this script started editing that file by hand during a live
# recording an hour before writing this, on the reasoning that it was only a
# comment. The digest does not care, deliberately: its own test says a
# comment-only edit must trip it. So the check is mechanical rather than
# remembered.
#
# CI never has a recording in flight, so this costs nothing there.
if pgrep -f "run_epoch.py" >/dev/null 2>&1 && [ "${ALLOW_DURING_RECORDING:-}" != "1" ]; then
    echo "a recording is in flight; this script mutates a frozen engine file." >&2
    echo "wait for it, or set ALLOW_DURING_RECORDING=1 if you know it is safe." >&2
    exit 2
fi

PY=./.venv/bin/python
M="$PY scripts/mutation_check.py --source datasets/merrick/build_tasks.py"
B="$PY scripts/mutation_check.py --source datasets/merrick/baselines.py"
fail=0

run() { echo; echo "── $1"; shift; "$@" || fail=1; }

run "_refuse_empty_answer — an oracle with no rows passes every other gate" \
  $M --tests tests/datasets/test_an_empty_oracle_is_refused.py \
     --function _refuse_empty_answer \
     --mutation 'if not rows[0]:' 'if False:' \
     --mutation 'if len(rows) != 1:' 'if False:'

run "_refuse_a_register_too_thin_to_grade — under twelve rows cannot score partially" \
  $M --tests tests/datasets/test_a_register_too_thin_to_grade_is_refused.py \
     --function _refuse_a_register_too_thin_to_grade \
     --mutation 'if not thin:' 'if True:' \
     --mutation 'and isinstance(value[0], dict)' 'and True'

run "_refuse_leaked_rows — a brief must not name a row the oracle scores" \
  $M --tests tests/datasets/test_briefs_do_not_print_answers.py \
     --function _refuse_leaked_rows \
     --mutation 'if not isinstance(rows, list) or not key_fields:' 'if False:'

run "_named_in — a longer identifier is not the same identifier" \
  $M --tests tests/datasets/test_briefs_do_not_print_answers.py \
     --function _named_in \
     --mutation 'if len(value) < 4 or value.isdigit():' 'if False:' \
     --mutation 'return re.search(rf"(?<![\w!.-]){re.escape(value)}(?![\w!.-])", text) is not None' 'return value in text'

run "_refuse_dead_categories — a table row the world never fills" \
  $M --tests tests/datasets/test_dead_category_gate.py \
     --function _refuse_dead_categories \
     --mutation 'if isinstance(count, (int, float)) and not count' 'if False' \
     --mutation 'surprising = [entry for entry in dead if entry not in allowed]' 'surprising = list(dead)'

run "_refuse_if_the_solver_refused — a staged solver's refusal must be legible" \
  $M --tests tests/datasets/test_a_solver_refusal_is_reported.py \
     --function _refuse_if_the_solver_refused \
     --mutation 'if outcome.returncode == 0:' 'if outcome.returncode != 0:' \
     --mutation 'said = (outcome.stderr or outcome.stdout or "").strip().splitlines()' 'said = []'

run "_refuse_a_key_that_no_longer_reproduces — regression, or a later world?" \
  $M --tests tests/datasets/test_an_oracle_names_the_world_it_came_from.py \
     --function _refuse_a_key_that_no_longer_reproduces \
     --mutation 'if stamp.get("sha256") and stamp["sha256"] == current["sha256"]:' 'if False:'

run "_commit_oracle — the stamp is written, and rolls back with its key" \
  $M --tests tests/datasets/test_an_oracle_names_the_world_it_came_from.py \
     --function _commit_oracle \
     --mutation 'stamp_path.write_text(json.dumps(_world_identity(), indent=1) + "\n")' 'pass' \
     --mutation 'for path, before in ((oracle_path, existing), (stamp_path, existing_stamp)):' 'for path, before in ((oracle_path, existing),):'

run "_world_identity — content, not the path it was read from" \
  $M --tests tests/datasets/test_an_oracle_names_the_world_it_came_from.py \
     --function _world_identity \
     --mutation 'digest = hashlib.sha256(log.read_bytes()).hexdigest()' 'digest = hashlib.sha256(str(log).encode()).hexdigest()'

run "refuse_a_task_a_dump_can_pass — a floor that reaches the band" \
  $B --tests tests/datasets/test_a_floor_that_reaches_the_band_is_refused.py \
     --function refuse_a_task_a_dump_can_pass \
     --mutation 'if not floors:' 'if False:' \
     --mutation 'if UNMEASURABLE in floors:' 'if False:' \
     --mutation 'dump >= DUMP_CEILING' 'dump > DUMP_CEILING'

run "baselines.measure — a dump that is secretly the oracle" \
  $B --tests tests/datasets/test_a_floor_is_absent_rather_than_invented.py \
     --function measure \
     --mutation 'if candidates <= len(truth):' 'if False:' \
     --mutation 'or k.endswith("_reviewed")' ''

# The engine's own refusals. These turned out to hold most of the gaps: a
# sweep on 2026-08-23 found 23 of grounded.py's 44 rejection sites with no
# test at all, including the fingerprint that stops a world being spliced
# out of two rule sets and the guard added after a recording was thrown
# away. None of them crash -- they shape the corpus, or protect a build
# hours downstream -- which is why a 652-test suite stayed green through
# every one.
G="$PY scripts/mutation_check.py --source src/simulation/gm/grounded.py"
R="$PY scripts/mutation_check.py --source src/simulation/run.py"

run "resume refuses an engine change, and records what to compare" \
  $R --tests tests/simulation/test_run_resume.py \
     --mutation 'if stored_engine and stored_engine != current_engine and not allow_engine_change:' 'if False:' \
     --mutation 'store.set_meta("engine_fingerprint", engine_fingerprint())' 'pass'

run "only the people in the room speak" \
  $G --tests tests/simulation/test_only_the_people_in_the_room_speak.py \
     --function _ground_meeting_speak \
     --mutation 'if entity not in progress.attendees:' 'if False:' \
     --mutation 'raise IntentRejection(f"no open meeting {intent.meeting_ref!r}")' 'return ()'

run "a mail thread stops growing, and its references resolve" \
  $G --tests tests/simulation/test_a_thread_stops_growing.py \
     --function _ground_email \
     --mutation 'if length >= 12:' 'if length >= 120:' \
     --mutation 'if parent_thread != thread_id:' 'if False:' \
     --mutation 'if self._world.resolve_document(ref) is None:' 'if False:'

run "chat refuses a reference it cannot resolve" \
  $G --tests tests/simulation/test_chat_refuses_a_reference_it_cannot_resolve.py \
     --mutation 'if intent.reply_to_ref not in self._world.chat_messages:' 'if False:' \
     --mutation 'resolved = self._world.resolve_conversation(message_ref)' 'resolved = None'

run "a day's plan lands inside the working day" \
  $G --tests tests/simulation/test_a_plan_lands_inside_the_working_day.py \
     --function _ground_agent_plan \
     --mutation 'if not clamped:' 'if False:' \
     --mutation 'sorted(intent.blocks, key=lambda b: (b.start, b.end))' 'intent.blocks' \
     --mutation 'if end <= start:' 'if False:'

run "a dropped timesheet entry is counted, not silently lost" \
  $G --tests tests/simulation/test_a_dropped_timesheet_entry_is_counted.py \
     --function _ground_timesheet \
     --mutation 'dropped_entries=len(unknown),' 'dropped_entries=0,' \
     --mutation 'unknown_refs=tuple(sorted(set(unknown))),' 'unknown_refs=(),'

run "the workplace vocabulary stays closed" \
  $G --tests tests/simulation/test_the_referee_refuses_a_reference_it_cannot_resolve.py \
     --mutation 'raise IntentRejection(f"unknown ticket status {create.status!r}")' 'pass' \
     --mutation 'raise IntentRejection(f"unknown priority {change.new!r}")' 'pass' \
     --mutation 'if intent.respond.calendar_event_ref not in self._world.calendar_events:' 'if False:'

echo
if [ "$fail" -eq 0 ]; then
    echo "every gate refuses when broken"
else
    echo "SOME GATE DID NOT NOTICE BEING BROKEN" >&2
fi
exit "$fail"

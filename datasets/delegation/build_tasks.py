"""Build Merrick Stanton task environments from its world log.

    uv run python datasets/merrick/build_tasks.py [--task NAME ...]

Materializes one seatless bundle from the epoch log and stages it for
every task under ``tasks/`` — seatless because these are firm-wide audits
that read across seats, the same choice the Hartwell tasks make. Each
task's reference solver runs against the fresh bundle and its output must
match the committed oracle byte for byte; ``--refresh-truth`` is the only
way to move that line, and it is a deliberate act.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import baselines

from analysis import attempted_work
from analysis.artifact_mix import MixFloors, emptiness, measure, violations
from analysis.calendar_units import inspect as inspect_calendar_units
from analysis.coherence import MISBOOKED_LIMIT, check
from analysis.fidelity import (
    evaluate,
    load_bands,
    summarize,
)

# Aliased: `analysis.artifact_mix.measure` is already imported above under
# that name, and importing this one plainly shadowed it -- the artifact
# check then failed with an unexpected keyword rather than a name error,
# which reads like the caller is wrong.
from analysis.fidelity import measure as measure_bands
from analysis.reachability import unreachable
from analysis.world_facts import load_world
from core.errors import WorldLogIntegrityError
from core.filing import filed_name
from core.worldlog import read_events
from environment.materialize import materialize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hartwell"))

from harbor_stage import stage  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
# The shared grading module. Every task's `criteria.py` puts its own
# `tests/` directory on `sys.path` and imports this by name, so a copy has
# to sit beside it in the staged task -- see `_ship_grading_base`.
CRITERIA_BASE = Path(__file__).resolve().parent / "criteria_base.py"
# The invocation layer. Declaring a criterion and registering one are
# different acts: the decorators in `criteria_base` make `rk.row_f1(...)`
# available, and something has to call it with this task's oracle before
# Reward Kit has a reward to compute. Without these three files a task
# discovers **zero** rewards and every trial returns no score at all.
GRADING = Path(__file__).resolve().parent / "grading"
# Derived from this dataset's own directory name rather than written out,
# so a second dataset built from the same machinery cannot silently share
# the first one's bundle. It did, for one build: a copy of merrick's
# builder pointed at merrick's bundle while claiming to build a different
# world, and every oracle it produced was merrick's.
DATASET = Path(__file__).resolve().parent.name
SHARED_BUNDLE = REPO / "out" / DATASET / "bundle"
_SOURCE = SHARED_BUNDLE / "SOURCE"
# The world the current bundle was built from, as the last build recorded
# it. A fixed default here meant `--refresh-truth` re-derived every oracle
# from `epoch/` while the bundle the tasks actually ship came from
# `epoch-r12` — a fresh answer key against a stale world, and nothing in
# the pipeline would have said so. The coherence gate happened to refuse
# (the old world is 20.7% mis-booked), which is luck, not a check.
DEFAULT_LOG = (
    Path(_SOURCE.read_text().strip())
    if _SOURCE.is_file()
    else REPO / "out" / DATASET / "world.jsonl"
)
# What this firm's file room must look like before any task is cut from
# it. Set against a measured known-bad — a recorded world whose 52
# documents materialized as 20 markdown, 19 workbooks, 10 unparseable
# `.txt` fallbacks and no documents, decks or issued PDFs at all.
#
# `.pptx` is required rather than merely permitted because this firm
# presents: to boards, to insurers, to a client's committee. A world that
# produces none of them has quietly dropped a whole kind of work an agent
# would otherwise have to do.
FILE_ROOM = MixFloors(
    max_markdown_share=0.15,
    min_office_share=0.70,
    max_fallbacks=0,
    required_forms=(".docx", ".xlsx", ".pptx", ".pdf"),
)


def degenerate(answer: dict) -> list[str]:
    """Row fields that carry the same value in every row.

    A constant column is a criterion that grades nothing: an agent that
    never looks it up and writes the majority value scores full marks on
    it. Both new tasks this dataset gained were degenerate on their first
    real world — 88 of 90 documents undelivered, and not one workpaper
    with a second author — and both looked healthy right up until the
    distributions were counted.

    Reported rather than fatal. Sparseness can be the finding (few
    documents ever reach a client, and that is the point), so this is a
    number for a person to weigh, not a gate to trip.
    """

    reports = []
    for key, rows in answer.items():
        if not isinstance(rows, list):
            continue
        if not rows:
            # The most degenerate answer of all, and the one this check used
            # to skip: an empty list grades nothing, and every agent that
            # reports nothing is exactly right. engagement-status-integrity
            # found no backward move at all in the r12 world and its answer
            # went out empty, which looked like a passing build.
            reports.append(f"{key} is EMPTY — there is nothing to find")
            continue
        if not isinstance(rows[0], dict):
            continue
        # A handful of rows cannot produce a partial score. Six of seven
        # tasks here answered with four to ten rows and every rollout came
        # back 1.000 or near zero: with so little to get partly right, the
        # grade is a verdict on the rule and not a measure of the work.
        if len(rows) < 12:
            reports.append(
                f"{key} has only {len(rows)} rows — too thin for partial credit"
            )
        if len(rows) < 5:
            continue
        for field in rows[0]:
            values = {json.dumps(row.get(field), sort_keys=True) for row in rows}
            if len(values) == 1:
                reports.append(
                    f"{key}.{field} is {values.pop()} in all {len(rows)} rows"
                )
    return reports


def build(
    world_log: Path,
    names: list[str],
    refresh: bool,
    allow_band_absence: bool = False,
) -> int:
    # Before anything is materialized: does the record contradict itself?
    # The materializer has its own integrity check and it caught the same
    # class once, but it speaks in sequence numbers. This reads the world as
    # facts and says which ticket, which field, and what the record actually
    # held -- and it separates the contradictions, which block, from the
    # ambiguities, which are the raw material the hardest tasks are made of.
    facts = load_world(world_log)
    found = check(facts)
    print(found.report())
    if not found.ok:
        reasons = []
        if found.contradictions:
            reasons.append(f"{len(found.contradictions)} contradiction(s)")
        if found.dangling:
            reasons.append(f"{len(found.dangling)} dangling reference(s)")
        if found.misbooked_share > MISBOOKED_LIMIT:
            reasons.append(
                f"{found.misbooked_share:.1%} of client time booked against an "
                "engagement its own note contradicts"
            )
        raise SystemExit(
            f"{'; '.join(reasons)}. This world cannot be graded: the answer "
            "would depend on which of two irreconcilable statements the agent "
            "happened to read."
        )

    # Wholesale, because materialize only *writes* files and never removes
    # them. Three worlds had been recorded into this one directory and it
    # had accumulated 161 files from a record that holds 52 documents —
    # every workbook and memo from epoch-r10 and r11 still sitting there,
    # describing engagements at statuses the live record left behind.
    #
    # Nothing noticed for as long as every task read `state/`, which is
    # rebuilt from scratch each time. The first task to grade the working
    # papers themselves would have keyed its oracle to two dead worlds.
    shutil.rmtree(SHARED_BUNDLE / "workspace", ignore_errors=True)
    shutil.rmtree(SHARED_BUNDLE / "state", ignore_errors=True)
    env = materialize(world_log, SHARED_BUNDLE, seat=None)
    print(f"materialized {env.event_count} events -> {SHARED_BUNDLE}")
    # Immediately, not after the gates. `materialize` has already rewritten
    # `workspace/` and `state/` wholesale, so from this line on the bundle
    # on disk *is* this world — and a gate that raises below would have
    # left SOURCE naming the previous one. That is exactly the "fresh
    # answer key against a stale world" state this file's other comment
    # exists to prevent, reached by a different route.
    (SHARED_BUNDLE / "SOURCE").write_text(str(world_log.resolve()) + "\n")

    # After materialize, and after SOURCE. Both gates read the *served*
    # state, which materialize is what builds -- run earlier they read
    # whatever the last build left behind, and one did: a state directory
    # thirty-one hours old, from before the projection learned to
    # quarantine malformed calendar starts, so the gate refused a world
    # over events the current projection drops.
    #
    # After SOURCE rather than before it, which is the correction. The
    # comment above says SOURCE must be written the moment the bundle on
    # disk becomes this world, and these two gates were inserted between
    # the two -- so a world that failed either left SOURCE naming the
    # previous one. That is the "fresh answer key against a stale world"
    # state this file exists to prevent, reached by the route the file was
    # already warning about.
    _calendar_units(world_log, SHARED_BUNDLE / "state")
    _realism_bands(SHARED_BUNDLE / "state", world_log, allow_absence=allow_band_absence)

    files = sum(1 for p in (SHARED_BUNDLE / "workspace").rglob("*") if p.is_file())
    print(f"  workspace: {files} files from {len(facts.documents)} documents")

    # The file room, before anything is cut from it. A world that is mostly
    # notes, or that is missing a form this firm really produces, or that
    # holds a single file claiming a form it does not have, is not this
    # firm — and every one of those failures is invisible until an agent
    # opens the folder.
    # Before the file room: did the record keep what the day actually
    # contained? A referee that rejects references the world does not
    # offer is behaving correctly and still leaves the record short, and
    # nothing downstream can tell the difference — a utilisation figure
    # over the survivors is self-consistent and describes another firm.
    notes, logged = [], 0
    for event in read_events(world_log):
        if event.tag == "sim.gm.note":
            notes.append(event.payload)
        elif event.tag == "work.time.logged":
            logged += 1
    work = attempted_work.measure(notes, logged=logged)
    print(
        f"  timekeeping: {work.logged} logged, {work.dropped} dropped "
        f"({work.dropped_share:.1%})"
    )
    wrong = attempted_work.violations(work)
    if wrong:
        raise SystemExit(
            "this world lost work it was asked to record:\n  - " + "\n  - ".join(wrong)
        )

    mix = measure(
        SHARED_BUNDLE / "workspace",
        declared=len(facts.documents),
        # Distinct *filed names*, not distinct declared paths. The file
        # room keeps only the top-level segment, so two documents can
        # declare different paths and produce one file — counting declared
        # paths reported those as "produced no file at all", which sends
        # the reader hunting a renderer bug in a world whose renderer is
        # fine.
        distinct_paths=len(
            {
                filed_name(d.path, getattr(d, "content_format", "markdown"))
                for d in facts.documents.values()
            }
        ),
    )
    print(f"  file room: {dict(mix.by_suffix)}")
    wrong = violations(mix, FILE_ROOM)
    if wrong:
        raise SystemExit(
            "the file room is not this firm's:\n  - " + "\n  - ".join(wrong)
        )
    # Reported, not refused. An empty file is content the generator never
    # wrote and a projection cannot invent it, so while the writer is frozen
    # this would block the only build available without fixing anything --
    # the same mistake a raw-rate calendar gate made here before it was
    # re-aimed at what actually reaches the served state. No task grades
    # document content today; one that did would have to check this itself.
    for lost in emptiness(mix):
        print(f"  file room: {lost}")
    if env.skipped_renders:
        for skip in env.skipped_renders:
            print(f"  render skipped: {skip}")

    # `_template` is the shape a task takes, not a task. Leading
    # underscore rather than a name on a list, so a second one cannot be
    # forgotten.
    available = sorted(
        p.name for p in TASKS.iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    if names:
        unknown = [name for name in names if name not in available]
        if unknown:
            # A mistyped selector used to print "no reference solver;
            # skipping" and exit 0 — a build that gated nothing, reported
            # success, and looked exactly like a build that gated
            # everything.
            raise SystemExit(
                f"no such task(s): {unknown}. Available: {available or '(none)'}"
            )
    # A retired task is kept for the measurement that retired it, and it
    # is not built. Several are unfinished scaffolds -- «MEASURE» notes
    # where a rule belongs -- so the staged-task gate below refused them
    # by name and the whole build died. `retired = true` had never been
    # READ anywhere: the word appeared once in this file, inside a
    # docstring. A flag with no reader.
    #
    # The effect was that `build_tasks.py` with no arguments could not
    # complete at all, and only `--task <name>` worked. Building everything
    # is what proves the tasks still agree with the world after a rule
    # changes, so the entry point that does it had quietly stopped
    # existing.
    #
    # Named explicitly, a retired task still builds: asking for one by
    # name is a deliberate act, and refusing it would make the measurement
    # that retired it unreproducible.
    retired = []
    if not names:
        for name in list(available):
            manifest = TASKS / name / "task.toml"
            if manifest.is_file() and re.search(
                r"^retired\s*=\s*true", manifest.read_text(), re.M
            ):
                available.remove(name)
                retired.append(name)
        if retired:
            # Printed, never silent. A task vanishing from a build without
            # a word is how a live task gets retired by a stray edit.
            print(f"skipping {len(retired)} retired task(s): {', '.join(retired)}")

    selected = names or available
    if not selected:
        # An audit that iterates an empty set passes vacuously, and this
        # one iterates the task directory. With no tasks, oracle
        # verification, reachability and degeneracy never run, and `build`
        # returns 0 having checked only the world.
        raise SystemExit(
            f"no tasks under {TASKS} — nothing was verified, staged or "
            "graded. A build with nothing to build is not a passing build."
        )
    # A staged task is not a task. Its corpus-dependent values are
    # `measure(...)` calls that raise and `«MEASURE»` notes in the brief,
    # both deliberate — but a build that stages one produces an oracle
    # from a solver that cannot run, or an instruction with a placeholder
    # where a rule belongs, and the agent is graded against it anyway.
    unfilled = []
    for name in selected:
        task = TASKS / name
        brief = task / "instruction.md"
        if brief.is_file() and "\u00abMEASURE" in brief.read_text():
            unfilled.append(f"{name}: instruction.md still has a placeholder")
        for source in sorted(task.rglob("*.py")):
            body = source.read_text()
            # A call, not a mention: docstrings describing what to measure
            # are how the task says what it still needs.
            if 'measure("' in body.replace('# measure("', ""):
                unfilled.append(f"{name}: {source.name} still calls measure()")
                break
    if unfilled:
        raise SystemExit(
            "these tasks are staged, not finished — their corpus "
            "measurements have not been made:\n  - " + "\n  - ".join(unfilled)
        )

    print(f"building {len(selected)} task(s)")
    for name in selected:
        task = TASKS / name
        solver = task / "solution" / "solve.py"
        if not solver.exists():
            raise SystemExit(
                f"{name}: no reference solver at {solver}. Its oracle cannot "
                "be verified, so shipping it would grade against an answer "
                "key nothing checked."
            )
        produced = SHARED_BUNDLE / "workspace" / f"{name}-answer.json"
        # Captured and re-raised as the solver's own words. The staged check
        # above knows two shapes of placeholder -- `«MEASURE` in the brief
        # and a `measure("` call in Python -- and a task can use a third:
        # a module constant left as `None` that `main()` refuses on. Such a
        # task passes the check, gets built, and dies here as a
        # `CalledProcessError` traceback naming a subprocess and an exit
        # code, twenty lines from the one sentence that says which value is
        # missing.
        #
        # The check is not widened to catch the third shape because it
        # cannot be: the `«MEASURE` text in a solver is *guidance for whoever
        # fills it* and stays there after filling, so flagging it would
        # report every finished task as staged. Reporting the refusal the
        # solver already writes is both simpler and exact.
        outcome = subprocess.run(
            [sys.executable, str(solver), str(produced)],
            check=False,
            capture_output=True,
            text=True,
            env={
                "WORKBENCH_STATE": str(SHARED_BUNDLE / "state"),
                # The working papers are files, not a surface. A solver
                # that grades them needs the same folder the agent gets.
                "WORKBENCH_WORKSPACE": str(SHARED_BUNDLE / "workspace"),
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            },
        )
        _refuse_if_the_solver_refused(name, outcome)
        answer = json.loads(produced.read_text())
        produced.unlink()
        oracle_path = task / "tests" / "oracle.json"
        # Compared now, written at the very end. Writing here left the file on
        # disk when any later gate raised, and the next build found it,
        # compared it equal to the same solver output, and printed "oracle
        # verified" -- a key that had never passed reachability, degeneracy or
        # the second derivation, wearing the word verified.
        fresh = refresh or not oracle_path.exists()
        if not fresh:
            _refuse_a_key_that_no_longer_reproduces(name, oracle_path, answer)

        _refuse_empty_answer(answer, name)
        _refuse_leaked_rows(task, answer, name)
        _refuse_dead_categories(task, answer, name)

        # An oracle the tools cannot spell is not an answer key, it is a
        # coin flip on which internal vocabulary the agent guesses. This
        # blocks the task rather than letting it produce a plausible score.
        missing = unreachable(
            answer, SHARED_BUNDLE / "state", SHARED_BUNDLE / "workspace"
        )
        if missing:
            raise SystemExit(
                f"{name}: the oracle names {len(missing)} value(s) no tool "
                f"ever serves: {missing[:8]}. Express the rule in something "
                "the surfaces expose, or the score measures the guess."
            )
        print(f"{name}: oracle reachable through the tools")

        for report in degenerate(answer):
            print(f"{name}: DEGENERATE {report}")
        _refuse_a_register_too_thin_to_grade(answer, name)

        _commit_oracle(task, name, answer, oracle_path, fresh)

        bundle = task / "bundle"
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.copytree(SHARED_BUNDLE, bundle)
        staged = stage(bundle, task / "environment", repo_root=REPO)
        print(f"{name}: staged -> {staged}")
    return 0


# The raw rate is reported at any level and refused at none. The writer is
# frozen mid-recording and cannot be fixed, so a world with malformed starts
# is the world there is; what has to hold is that none of them reaches
# anything that ships. That is checked directly below rather than proxied by
# a threshold, because a threshold can be satisfied by moving it.


# Bands whose absence refuses this world, and why each one earns it.
#
# The committed band file was written for a seventeen-person *accounting*
# firm. Merrick is a law firm with ten clients and fifty-three matters by
# design, so `book.clients: 10 against 120-200` is a band that does not
# apply rather than a defect, and `cross.weekend_share_busy` is measuring
# a February-to-April tax season this firm does not have. Refusing on all
# 37 current failures would refuse every world this dataset can produce.
#
# Two bands survive that filter. Both describe a capability a law firm
# certainly has, both measured exactly zero, and both were zero because
# the engine could not produce them at all rather than because the firm
# was quiet:
#
#   slack.dm_share             the generic compile path had no way to make
#                              a DM, so 3,177 messages were posted in the
#                              open across ten channels
#   slack.threaded_reply_share pending chat items offered a conversation
#                              id where the reply branch needed a message
#                              id, so 3 messages in 3,177 were replies
#
# Deliberately excluded, and worth naming so nobody adds them later
# expecting them to work: `calendar.cancellation_share` has no cancel verb
# anywhere in the engine, so it is unsatisfiable by construction, and a
# gate that cannot pass is a gate that gets deleted in a hurry by whoever
# meets it next.
_STRUCTURAL_BANDS = (
    "slack.dm_share",
    "slack.threaded_reply_share",
)


def _named_in(value: str, text: str) -> bool:
    """Whether `text` names this value, as opposed to containing its
    characters.

    A bare integer cannot be evidence. The first version of this check
    reported three tasks as leaking the keys `1`, `2`, `5` and `12` --
    every one of which appears in any prose of any length. Reporting them
    would have sent somebody rewriting good briefs, which costs the same
    as the leak the gate exists to stop.
    """

    if len(value) < 4 or value.isdigit():
        return False
    return re.search(rf"(?<![\w!.-]){re.escape(value)}(?![\w!.-])", text) is not None


def _refuse_leaked_rows(task: Path, answer: dict, name: str) -> None:
    """A brief must not print a row key the oracle scores.

    `no-op-revision-register` illustrated its output shape with
    `"document_ref": "LEGAL!12.3"`, and `LEGAL!12.3` was one of the twenty
    true rows. Row F1 keys on `document_ref` alone, so the brief handed
    every reader one row of recall and its three graded fields, for
    reading the example.

    A worked example is worth having and the fix is not to drop it — it is
    to make sure the example names nothing real. The author cannot check
    that by eye, because the oracle is re-derived every time the world is,
    and a value that was safe last month is a row this month.

    Only row *keys* are checked. Scalars are a different question with a
    different answer: `window_end` appears in the brief because the brief
    states the window, which is why it is graded in the diagnostic
    dimension rather than the reward -- see `RESTATED_FROM_BRIEF`.
    """

    brief = task / "instruction.md"
    criteria = task / "tests" / "criteria.py"
    if not brief.is_file() or not criteria.is_file():
        return
    rows_key = _literal_in(criteria, "ROWS")
    key_fields = _literal_in(criteria, "KEY") or ()
    rows = answer.get(rows_key) if rows_key else None
    if not isinstance(rows, list) or not key_fields:
        return
    text = brief.read_text(encoding="utf-8")
    # A row is identified by its whole key, not by one component of it.
    # Run across the other dataset in this tree, the first version flagged
    # a brief for printing `00004-KestrelManufacturing` — one half of a
    # ("engagement", "person") key with seventeen rows under it, and the
    # very string the brief has to name to explain the join the task is
    # about. Removing it would have made the brief unusable to fix a leak
    # that was not one.
    #
    # So a composite key leaks only when its components appear together on
    # one line, which is what naming a row looks like.
    lines = text.splitlines()
    if len(key_fields) == 1:
        (field,) = key_fields
        values = {
            str(row[field]) for row in rows if isinstance(row, dict) and row.get(field)
        }
        found = {v for v in values if _named_in(v, text)}
    else:
        values = {
            " / ".join(str(row.get(f, "")) for f in key_fields)
            for row in rows
            if isinstance(row, dict)
        }
        found = {
            label
            for label, parts in (
                (v, [str(row.get(f, "")) for f in key_fields])
                for v, row in zip(
                    values, [r for r in rows if isinstance(r, dict)], strict=False
                )
            )
            if all(p for p in parts)
            and any(all(_named_in(p, line) for p in parts) for line in lines)
        }
    # A bare integer cannot be evidence. Run across the other dataset in
    # this tree, the first version of this check reported three tasks as
    # leaking keys `1`, `2`, `5` and `12` -- every one of which appears in
    # any prose of any length, and none of which tells a reader anything.
    # Reporting them would have sent somebody rewriting good briefs, which
    # is the same cost as the leak this gate exists to stop.
    #
    leaked = sorted(found)
    if leaked:
        raise SystemExit(
            f"{name}: instruction.md prints {len(leaked)} row key(s) the "
            f"oracle scores: {leaked[:5]}. A worked example must name "
            "nothing the answer contains, or the brief is worth marks."
        )


def _literal_in(path: Path, name: str):
    """One module-level literal, read without importing the module."""

    import ast

    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError:
                        return None
    return None


def _structural_absences(results, *, report: bool = True) -> list[str]:
    """Which structural bands say this world has none of that thing.

    Split out so a test can drive the decision without building a world.
    The first version of that test restated this loop instead, which is
    the shape of defect this file has spent the day finding: two readers
    of one rule, agreeing with each other and with nothing else.

    **ABSENT counts, not only FAIL.** A metric whose surface is missing,
    or present and holding no rows, measures None and is scored ABSENT --
    never FAIL -- so filtering on FAIL skipped the strongest form of the
    absence this gate exists to catch. A world with no chat surface at all
    passed; a world with a chat surface reading 0.0 did not.
    """

    missing: list[str] = []
    for result in sorted(results, key=lambda r: r.metric):
        if result.metric not in _STRUCTURAL_BANDS or result.verdict == "PASS":
            continue
        if report:
            observed = (
                "not measurable" if result.observed is None else f"{result.observed}"
            )
            print(
                f"    structural {result.metric}: {observed} "
                f"vs {result.band.rendered()} [{result.verdict}]"
            )
        if result.verdict == "ABSENT":
            missing.append(
                f"{result.metric} could not be measured at all — the surface "
                "it reads is missing or empty"
            )
            continue
        # Not `== 0`. The first version refused only an exact zero, and the
        # world it was written for measured `threaded_reply_share` at
        # 0.000315 -- three threaded replies in 3,177 messages, every one a
        # fluke of a code path that could not fire on purpose. Absence had
        # been rounded into presence by three accidents, and only
        # `dm_share` landing on exactly 0.0 caught the world at all.
        #
        # A tenth of the floor is the line between "the engine cannot do
        # this" and "the firm was quiet": 0.25 against a floor of 0.30 is a
        # realism note, 0.0003 is a missing feature.
        if result.band.min and result.observed < result.band.min / 10:
            missing.append(
                f"{result.metric} is {result.observed:.4g}, effectively none "
                f"against a band of {result.band.rendered()}"
            )
    return missing


def _realism_bands(
    state_dir: Path, world_log: Path, *, allow_absence: bool = False
) -> None:
    """The committed distribution bands, run against the world just built.

    These bands have existed, and been computed correctly, for as long as
    this tree has. Nothing in a build ever ran them. Their only caller was
    a realism suite pointed at a *different firm's* world and marked
    xfail, so the verdict it produced could not fail anything even on the
    occasions somebody read it.

    What that cost here: six months of a law firm shipped with
    `slack.dm_share` at 0.0 against a band of 0.15-0.35 and
    `slack.threaded_reply_share` at 0.0 against a floor of 0.30. Both
    numbers were right. Nobody was looking at them.

    **Refuse on a declared absence, report on everything else.** A band
    missed by a margin is a realism note and a judgement call. A band in
    `_STRUCTURAL_BANDS` sitting at zero says the world has none of that
    thing at all -- which is the failure this exists to catch, and the one
    that hides best, because an empty column raises nothing anywhere.
    """

    measurements = measure_bands(state_dir, world_log)
    results = evaluate(measurements, load_bands())
    counts = summarize(results)
    print(
        f"  realism bands: {counts['PASS']} pass, {counts['FAIL']} fail, "
        f"{counts['ABSENT']} absent of {len(results)} "
        f"(most were written for an accounting firm; see _STRUCTURAL_BANDS)"
    )
    _report_undeclared_absences(results)
    missing = _structural_absences(results)
    if missing:
        message = "this world has none of something a firm certainly has: " + "; ".join(
            missing
        )
        if not allow_absence:
            raise WorldLogIntegrityError(message)
        # Loud, and named as a choice. A world recorded before the engine
        # could produce DMs is worth building to exercise the harness
        # against; it is not worth grading a model on.
        print(f"  ALLOWED (--allow-band-absence): {message}")
        print("    do not ship rollout numbers from this world")


def _report_undeclared_absences(results) -> None:
    """Bands that meet the structural-absence rule and are not on the list.

    `_STRUCTURAL_BANDS` is two entries long and hand-kept, and the comment
    above it says as much -- it is a list because *which* bands apply to a
    law firm is a judgement, and most of these were written for an
    accounting firm. That is a good reason for the gate's scope to be
    curated. It is not a reason for the gap to be invisible: nothing has
    ever prompted anyone to review the list against what the world actually
    reads, so a new absence joins the 36 failing bands and is never seen.

    Filtered to surfaces that **exist and read effectively nothing**, which
    is the class worth a person's attention: the world can do this and
    never does. A metric scored ABSENT has no surface at all -- the tax and
    billing bands here -- and is a band written for a different firm rather
    than a hole in this one. That single distinction takes the report from
    30 lines of mostly-noise to 9.

    On the v6 world it names, among others, `calendar.cancellation_share`
    at 0.000 -- not one meeting cancelled in sixty-eight days -- and
    `email.machine_share` at 0.000, a firm with no automated mail of any
    kind. Neither had ever been surfaced, because both are FAIL and the
    gate reads only its own two names.

    Reported, not refused, for the same reason the list is curated: whether
    a law firm should have CSVs is not something this function knows.
    """

    candidates = [
        result
        for result in sorted(results, key=lambda r: r.metric)
        if result.metric not in _STRUCTURAL_BANDS
        and result.verdict == "FAIL"
        and result.band.min
        and result.observed is not None
        and result.observed < result.band.min / 10
    ]
    if not candidates:
        return
    print(
        f"  {len(candidates)} surface(s) exist and read effectively nothing, "
        "and are NOT declared structural — review _STRUCTURAL_BANDS:"
    )
    for result in candidates:
        print(
            f"    {result.metric}: {result.observed:.4g} "
            f"against a floor of {result.band.min}"
        )


def _calendar_units(world_log: Path, state_dir: Path) -> None:
    """Report malformed calendar starts, and refuse if any reached the surface.

    Two wrong units turn up in this world's calendar: a wall-clock time of
    day that lost its date, and an absolute Unix timestamp. Neither raises --
    each is a plausible integer that projects into a plausible row -- and the
    served diary would otherwise hold meetings before the firm opened and
    meetings in 2081.

    An earlier version of this gate refused any world above a 2% raw rate.
    That was aimed wrongly on two counts. The rate is a property of a
    generator that cannot be changed while it runs, so refusing on it blocks
    the only build available rather than fixing anything. And the projection
    already quarantines these events, so the raw rate says nothing about what
    an agent can see: measured on this world at 14.9% raw, the served
    calendar held 723 events, every one inside the window, with the coherence
    checker finding nothing.

    So the question is not "how many did the generator write" but "did any
    survive into the state that ships". The first is reported because it is a
    real defect someone must fix; the second is refused because it is the one
    that would reach a score.
    """

    starts = [
        (event.payload.calendar_event_id, int(event.payload.start), int(event.time))
        for event in read_events(world_log)
        if event.tag == "calendar.event.scheduled"
    ]
    report = inspect_calendar_units(starts)
    print(f"calendar units: {report.summary()}")
    if not report.suspects:
        return

    served = state_dir / "calendar.db"
    if not served.is_file():
        raise SystemExit(
            f"{report.summary()}, and there is no served calendar to check "
            "them against. Project the state before gating it."
        )
    connection = sqlite3.connect(f"file:{served}?mode=ro", uri=True)
    try:
        survivors = sorted(
            {suspect.event_id for suspect in report.suspects}
            & {
                row[0]
                for row in connection.execute(
                    "SELECT calendar_event_id FROM calendar_events"
                )
            }
        )
    finally:
        connection.close()

    if survivors:
        raise SystemExit(
            f"{len(survivors)} calendar event(s) with a start that is not "
            f"seconds-from-epoch reached the served state: {survivors[:6]}. "
            "The projection is meant to quarantine these; a start in the "
            "wrong unit does not raise, it lands on day zero or fifty years "
            "out and serves as a real event, so every task reading a date "
            "would grade the defect."
        )
    print(
        f"calendar units: all {len(report.suspects)} quarantined before the "
        "served state — see docs/fidelity/post-freeze-fixes.md for the writer"
    )


def _world_identity() -> dict[str, str]:
    """Which world the bundle on disk was built from, by content.

    `SOURCE` names the world log as a path, and a path is a weak identity:
    `epoch-v7/world.jsonl` means one thing at day 40 and another at day
    180, and every recording in this project writes to a path it will
    later append to. The digest is what actually distinguishes two worlds,
    and it costs 0.12s on a 23M log -- a rounding error inside a build
    that materializes the whole file room.
    """

    source = _SOURCE.read_text().strip() if _SOURCE.exists() else ""
    if not source:
        return {"world_log": "", "sha256": ""}
    log = Path(source)
    if not log.exists():
        return {"world_log": source, "sha256": ""}
    digest = hashlib.sha256(log.read_bytes()).hexdigest()
    return {"world_log": source, "sha256": digest}


def _world_stamp_path(oracle_path: Path) -> Path:
    """Beside the oracle, not inside it.

    `criteria_base` does `TOP = frozenset(_ORACLE)` -- the oracle's
    top-level keys *are* the list of figures the report is graded on. A
    `_world` key added for provenance would become a figure every answer
    is missing, so the stamp has to live in its own file.
    """

    return oracle_path.with_suffix(".world")


def _refuse_a_key_that_no_longer_reproduces(
    name: str, oracle_path: Path, answer: dict
) -> None:
    """Two different failures wore one message, and one of them is a bug.

    The old text -- "the reference solver no longer reproduces its oracle.
    Rebuild the world or pass --refresh-truth deliberately" -- is printed
    both when the solver has regressed against the same world, which is a
    defect to go and find, and when the bundle is simply a later recording,
    which is expected and whose remedy is exactly the `--refresh-truth`
    the message offers. Conflating them trains the reader to reach for the
    refresh, and the refresh is what disables the check for the first case.

    So this asks the question the old line could not: *is it the same
    world?* Same world and a different answer is a regression and says so
    in those words. A different world says which one, and that re-deriving
    is the correct move rather than a workaround.
    """

    if json.loads(oracle_path.read_text()) == answer:
        return

    stamp_path = _world_stamp_path(oracle_path)
    stamp = json.loads(stamp_path.read_text()) if stamp_path.exists() else {}
    current = _world_identity()

    if stamp.get("sha256") and stamp["sha256"] == current["sha256"]:
        raise SystemExit(
            f"{name}: SOLVER REGRESSION. The oracle and the bundle are the "
            f"same world ({Path(current['world_log']).parent.name}, "
            f"sha {current['sha256'][:12]}) and the solver now returns a "
            "different answer. Something changed in the solver, the tools "
            "or the projection. Find it -- do NOT pass --refresh-truth, "
            "which would write the new answer down as truth unexamined."
        )

    was = stamp.get("world_log") or "an unrecorded world"
    if stamp.get("world_log"):
        was = f"{Path(was).parent.name} (sha {stamp.get('sha256', '')[:12]})"
    raise SystemExit(
        f"{name}: the oracle was derived from {was}; the bundle is "
        f"{Path(current['world_log']).parent.name} "
        f"(sha {current['sha256'][:12]}). A key for one world cannot grade "
        "another. Re-derive it with --refresh-truth -- that is the correct "
        "move here, not a way around the check."
    )


def _commit_oracle(
    task: Path, name: str, answer: dict, oracle_path: Path, fresh: bool
) -> None:
    """Write the answer key only if every remaining gate accepts it.

    The verifier reads the oracle off disk, so it has to be written before
    the gates that check it. It must not *survive* a gate that refuses:
    previously the file was written early and left behind by any later raise,
    so the next build found it, compared it equal to the same solver output,
    and announced "oracle verified" for a key that had never passed
    reachability or a second derivation.

    Restoring the previous contents rather than always deleting matters when
    a rebuild fails: an existing, good answer key should not be destroyed by
    a run that could not finish.
    """

    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    # The world stamp rolls back with the key it describes. Written outside
    # this try, a refused build would leave the new world named against the
    # restored old answer -- a key claiming a provenance it does not have,
    # which is worse than no stamp at all because the next build would then
    # read the two as the same world and call a re-derivation a regression.
    stamp_path = _world_stamp_path(oracle_path)
    existing = oracle_path.read_text() if oracle_path.exists() else None
    existing_stamp = stamp_path.read_text() if stamp_path.exists() else None
    written = json.dumps(answer, indent=1) + "\n"
    # An UNCHANGED key is not rewritten, and the reason is about
    # measurements rather than about disk.
    #
    # Every sweep on this tree is dated against the oracle it was graded on:
    # a reward file older than the key it was scored by came from a key that
    # no longer exists, which is the only staleness check that works when a
    # harness never records the prompt. Rewriting a byte-identical file
    # moves its mtime and retroactively invalidates every measurement ever
    # taken against it.
    #
    # It happened. A correction to the standing-series rule was propagated
    # to seven solvers and left three oracles byte-for-byte identical -- the
    # hashes were compared before and after and matched -- and the rebuild
    # still marked two CERTIFIED tasks as "graded against a superseded key",
    # discarding nine graded trials that were perfectly valid.
    if existing == written:
        try:
            _run_second_derivation(task, name, oracle_path)
            _ship_grading_base(task, name)
        except BaseException:
            raise
        print(f"{name}: oracle unchanged (mtime preserved)")
        floors = baselines.measure(task, answer)
        print("  " + baselines.render(name, floors))
        baselines.refuse_a_task_a_dump_can_pass(name, floors)
        return
    oracle_path.write_text(written)
    stamp_path.write_text(json.dumps(_world_identity(), indent=1) + "\n")
    try:
        _run_second_derivation(task, name, oracle_path)
        _ship_grading_base(task, name)
    except BaseException:
        for path, before in ((oracle_path, existing), (stamp_path, existing_stamp)):
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(before)
        raise
    print(f"{name}: oracle {'written' if fresh else 'verified'}")
    # What this task pays for answers that demonstrate nothing. A band is
    # only meaningful against its floor: measured on this dataset's own
    # shape, reporting every candidate with no comprehension at all scores
    # 0.427, which is inside the 0.2-0.8 band the tasks target. Printed
    # here so a rollout number is never read without it.
    #
    # And refused, not only printed. Printing was this line's whole job for
    # months, on the assumption that a number in the build log gets read --
    # the same assumption that let a whole other dataset be banded with no
    # floors at all, because the function returned an empty dict there and
    # an empty dict prints as one quiet line. A threshold is what makes a
    # measurement a gate.
    floors = baselines.measure(task, answer)
    print("  " + baselines.render(name, floors))
    baselines.refuse_a_task_a_dump_can_pass(name, floors)


def _refuse_dead_categories(task: Path, answer: dict, name: str) -> None:
    """A category the brief enumerates and the world never fills.

    Every dict-valued figure in these oracles is a *table the brief prints*
    — `form_counts` has one key per row of the admitted-forms table,
    `department_counts` one per department. A key whose count is zero means
    the brief spent a row of a table, and a paragraph of the reader's
    attention, on a rule this corpus never exercises. The key is then a
    constant: an agent that never looks writes 0 and scores full marks, and
    the rule it was meant to test is graded by nothing.

    Measured instances in this tree. `deadline-week-promise-clock` prints a
    form table whose `end of month` row matches **zero** of 2,717 mail
    messages — `end of month`, `end of the month` and `EOM` together. And a
    sibling firm's brief warned about the article form `end of the week`,
    which occurred fifteen times there and *not once* here, while the bare
    form occurred 172 times: a rule carried across worlds without being
    re-measured admits one instance in thirty-five and scores the rest as
    inventions.

    So this refuses rather than reports, which is the opposite of
    `degenerate()` above. A constant *row column* can be the finding —
    sparseness is real, and few documents ever reach a client. A dead
    *table row* cannot: the brief asserted a category exists, and it does
    not. That is a false statement about the world, and this dataset has
    shipped three of them.

    A task that genuinely means to test whether an agent reports an empty
    category says so, by name, in its `criteria.py`:

        ALLOWED_EMPTY_KEYS = ("form_counts.end of month",)

    Declared and narrow on purpose. `off-sense-register` requires every
    form as a key "including any that no narrative in the window uses", and
    that is a real thing to grade — once, deliberately, with the reason
    written down.
    """

    allowed = frozenset(
        baselines._literal_of(task / "tests" / "criteria.py", "ALLOWED_EMPTY_KEYS")
        or ()
    )
    dead = [
        f"{field}.{key}"
        for field, value in sorted(answer.items())
        if isinstance(value, dict)
        for key, count in sorted(value.items())
        if isinstance(count, (int, float)) and not count
    ]
    surprising = [entry for entry in dead if entry not in allowed]
    if surprising:
        raise SystemExit(
            f"{name}: the brief enumerates {len(surprising)} categor"
            f"{'y' if len(surprising) == 1 else 'ies'} the world never "
            f"fills: {surprising}. Each one is a table row the reader is "
            "told to apply and a key an agent scores by writing 0. Measure "
            "the corpus and drop the row, widen it until it admits "
            "something, or declare it in ALLOWED_EMPTY_KEYS with the reason."
        )
    stale = sorted(allowed - set(dead))
    if stale:
        # An allowance that no longer allows anything is a comment claiming
        # a defect that has been fixed, and the next reader believes it.
        print(
            f"{name}: note — ALLOWED_EMPTY_KEYS still lists {stale}, which "
            "this world does fill. Drop the allowance."
        )


def _refuse_empty_answer(answer: dict, name: str) -> None:
    """A task whose oracle has no rows passes every other gate.

    Reachability finds no unserved identifier because there are no
    identifiers. The second derivation agrees, because both sides produce
    nothing and nothing equals nothing. Degeneracy reports no constant field
    because there are no fields. Every check is satisfied and the task grades
    an empty register, where a model that writes `[]` scores 1.0 and a model
    that finds anything at all scores less.

    That is not hypothetical here: three tasks were retired for producing
    0-3 rows, and each was caught by measuring on purpose rather than by the
    build refusing.
    """

    rows = [value for value in answer.values() if isinstance(value, list)]
    if len(rows) != 1:
        raise SystemExit(
            f"{name}: expected exactly one list of rows in the oracle, found "
            f"{len(rows)} — the emptiness gate cannot tell what to count."
        )
    if not rows[0]:
        raise SystemExit(
            f"{name}: the oracle has no rows. Every other gate passes on an "
            "empty answer key — nothing is unreachable, both derivations "
            "agree, no field is constant — and the task then rewards an "
            "agent for reporting nothing. Widen the window or retire the rule."
        )


# Below this a register cannot produce a partial score: with so few rows to
# get partly right, one row's worth of F1 is a tenth of the criterion and
# the grade becomes a verdict on the rule. Kept equal to the threshold
# `degenerate` already reports at, so the report and the refusal cannot
# drift apart.
THIN_ROWS = 12


def _refuse_a_register_too_thin_to_grade(answer: dict, name: str) -> None:
    """`degenerate` has reported this for as long as it has existed.

    Its docstring even carries the evidence -- "six of seven tasks here
    answered with four to ten rows and every rollout came back 1.000 or
    near zero" -- and it reports rather than refuses, deliberately, because
    *sparseness can be the finding*: few documents ever reach a client, and
    a task about that should be allowed to say so.

    That justification is about a **constant column**. It was written for
    one of `degenerate`'s two report kinds and inherited by the other, and
    the other is not a finding about the world. A register of four rows
    does not tell you something surprising about the firm; it tells you the
    grade cannot be partial. The two reports travel together in one list
    and one of them earned the exemption.

    Measured downstream, in the dataset that has never gated on it:
    ashgrove ships five tasks under this threshold, `open-items-triage` at
    four rows and four more at ten. Both of the thin ones whose scores were
    published came back at or beside 1.000 across every model -- exactly
    what the report predicted, printed at build time, and shipped.

    This dataset's own three built tasks hold 20, 22 and 34 rows, so the
    refusal blocks nothing here today. It is for the next thin one.
    """

    # Every list, not just the one when there happens to be one. The first
    # version returned early unless the oracle held exactly one list, which
    # made it strictly weaker than the report it is built on: `degenerate`
    # counts each list separately, and four of ashgrove's five thin tasks
    # carry a second list, so they slipped past a check that was flagging
    # them one line above. In this dataset `_refuse_empty_answer` refuses a
    # two-list oracle outright, so the early return was also unreachable --
    # a dead branch that made the gate look narrower than it was.
    # Lists of *rows*, which is what `degenerate` counts and what the
    # threshold was measured on. A list of scalars is a set-membership
    # figure -- ashgrove grades four engagement numbers as a set, and a set
    # of four is a legitimate criterion rather than a register too thin to
    # score. Counting those refused four more ashgrove tasks than the
    # report this gate is supposed to be the teeth of, which is the gate
    # inventing its own rule rather than enforcing one.
    thin = {
        key: len(value)
        for key, value in answer.items()
        if isinstance(value, list)
        and value
        and isinstance(value[0], dict)
        and len(value) < THIN_ROWS
    }
    if not thin:
        return
    counted = ", ".join(f"{key} holds {n}" for key, n in sorted(thin.items()))
    raise SystemExit(
        f"{name}: {counted}, under the {THIN_ROWS} rows a register needs to "
        "score partially. Every rollout on a register this thin comes back "
        "at 1.000 or near zero, which is a verdict on the rule rather than a "
        "measure of the work. Widen the window, loosen the rule, or retire it."
    )


def _run_second_derivation(task: Path, name: str, oracle_path: Path) -> None:
    """Actually execute the task's independent verifier.

    Every task carries a `checks/verify.py` that derives the answer a second
    time, and a gate forbids it sharing rule literals with the solver. An
    audit then found the obvious thing nobody had checked: **nothing in the
    repository ever ran it.** The independence was real and entirely
    decorative -- a second derivation that never executes agrees with
    everything.

    Verifiers come in two shapes and both are driven the same way here. The
    longer ones read their state from the environment and ignore `argv`;
    the shorter ones take state, window and oracle as arguments. Passing
    all three satisfies the second and is harmless to the first.

    A disagreement fails the build. That is the whole point of deriving the
    answer twice: if the two derivations differ, one of them is wrong and
    neither should be shipped as an answer key.
    """

    verifier = task / "checks" / "verify.py"
    if not verifier.is_file():
        raise SystemExit(
            f"{name}: no second derivation at {verifier}. An oracle checked "
            "only by the code that produced it is not checked."
        )
    window = _declared_window(task)
    result = subprocess.run(
        [
            sys.executable,
            str(verifier),
            str(SHARED_BUNDLE / "state"),
            str(window),
            str(oracle_path),
        ],
        capture_output=True,
        text=True,
        env={
            "WORKBENCH_STATE": str(SHARED_BUNDLE / "state"),
            "WORKBENCH_WORKSPACE": str(SHARED_BUNDLE / "workspace"),
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        },
    )
    if result.returncode:
        # Exit 1 is the verifier's considered disagreement; anything else is
        # it failing to run. Reporting a crash as "the two derivations
        # disagree" sends the reader looking for a rule mismatch that is not
        # there.
        # Three outcomes, not two. A verifier that pins its assumptions to
        # the brief raises at *import* time when the brief has moved, and an
        # uncaught exception exits 1 -- indistinguishable from a considered
        # disagreement unless the output is read. Reporting a moved brief as
        # "the two derivations disagree" sends the reader hunting a rule
        # mismatch between two files that in fact agree with each other.
        output = (result.stdout + result.stderr).strip()
        pinned = any(
            marker in output
            for marker in (
                "no longer states",
                "BriefChanged",
                "BoundaryDisagreement",
                "RuleChanged",
                "has changed: pinned",
            )
        )
        if pinned:
            headline = (
                f"{name}: the brief no longer says what its verifier assumes. "
                "The two derivations were never compared -- this failed before "
                "they ran. Re-read the brief against checks/verify.py, then "
                "re-pin deliberately"
            )
        elif result.returncode != 1:
            headline = (
                f"{name}: the independent verifier could not run "
                f"(exit {result.returncode})"
            )
        else:
            headline = (
                f"{name}: the independent verifier disagrees with the reference "
                "solver, so one of the two is wrong and the oracle is not an "
                "answer key"
            )
        raise SystemExit(f"{headline}.\n{output[-1200:]}")
    print(f"{name}: second derivation agrees")


def _declared_window(task: Path) -> int:
    """The solver's own window, read without importing it.

    Importing would execute a staged solver's `measure()` calls and raise
    for a reason unrelated to verification, so the value is read off the
    source. A task whose window is still a placeholder never reaches here:
    the staged-task guard upstream refuses the build first.
    """

    source = (task / "solution" / "solve.py").read_text(encoding="utf-8")
    # Indentation is allowed. A solver may keep its window inside a function
    # so that the rest of the module -- date arithmetic, form tables -- stays
    # importable before the corpus exists; `live-commitment-register` does
    # exactly that, and its 20 unit tests depend on it. The name is what this
    # reads, not the column it starts in.
    found = re.search(r"^\s*WINDOW_DAYS[^=]*=\s*(\d+)", source, re.M)
    if found:
        return int(found.group(1))

    # Not every solver names its window the same way, and demanding one name
    # made the build refuse a task for a naming convention the build itself
    # invented. A window stated as an inclusive last-day index is the same
    # window, one off: day 0 through day N is N+1 days.
    last = re.search(r"^\s*WINDOW_LAST_DAY[^=]*=\s*(\d+)", source, re.M)
    if last:
        return int(last.group(1)) + 1

    raise SystemExit(
        f"{task.name}: its solver states no concrete window -- neither "
        "WINDOW_DAYS nor WINDOW_LAST_DAY -- so the verifier cannot be told "
        "which window to re-derive. If it names the window some third way, "
        "teach this function that name rather than renaming the solver."
    )


def _refuse_if_the_solver_refused(
    name: str, outcome: subprocess.CompletedProcess
) -> None:
    """Re-raise a solver's own refusal instead of a subprocess traceback.

    The staged check upstream knows two shapes of placeholder — `«MEASURE`
    in the brief, and a `measure("` call in Python. A task can use a third:
    a module constant left as `None` that `main()` refuses on. Such a task
    passes the check, gets built, and used to die here as a
    `CalledProcessError` naming a subprocess and an exit code, twenty lines
    from the one sentence that says which value is missing.

    Widening the check to catch the third shape is not possible: the
    `«MEASURE` text inside a solver is guidance for whoever fills it and
    stays there after filling, so flagging it would report every finished
    task as staged. The solver already writes the exact sentence; this
    carries it up.

    The last line, not the whole stream — a refusal is one sentence and a
    traceback above it is noise, while a solver that dies for some other
    reason still gets its final line reported rather than swallowed.
    """

    if outcome.returncode == 0:
        return
    said = (outcome.stderr or outcome.stdout or "").strip().splitlines()
    last = said[-1] if said else f"exit status {outcome.returncode}"
    raise SystemExit(f"{name}: its reference solver refused —\n  {last}")


def _ship_grading_base(task: Path, name: str) -> None:
    """Put the shared grading module beside the criteria that imports it,
    then prove the import actually works from a bare task directory.

    `criteria.py` does `sys.path.insert(0, <its own tests/ dir>)` and then
    `from criteria_base import *`. The module lives one directory up, in the
    dataset root, which is not on the grader's path -- so every criterion in
    every task raised `ModuleNotFoundError` on load. Nothing in the suite
    noticed, because the unit tests add the dataset root to `sys.path`
    themselves and import through a door the grader does not have.

    The consequence is the worst kind available here: no criterion loads, so
    every task scores zero, and a total wipeout reads as catastrophic model
    failure rather than as a missing file.

    The copy alone is not the fix. The check is, and it runs the import the
    way the grader will -- a subprocess whose path holds only the task's own
    `tests/` directory. A copy that silently stops happening is exactly the
    kind of thing that comes back.
    """

    tests = task / "tests"
    # answer/ and process/ are Reward Kit's two dimensions; test.sh is the
    # entrypoint that runs it. All three were missing from every task in this
    # dataset, so nothing invoked the criteria at all.
    for source, destination in (
        (GRADING / "grade.py", tests / "answer" / "grade.py"),
        (GRADING / "method.py", tests / "process" / "method.py"),
        (GRADING / "test.sh", tests / "test.sh"),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (tests / "test.sh").chmod(0o755)

    if not (tests / "criteria.py").is_file():
        raise SystemExit(
            f"{name}: no tests/criteria.py, so nothing grades this task. "
            "Returning quietly here made a task with no criteria a clean "
            "pass, which is the loudest kind of silence."
        )
    shutil.copyfile(CRITERIA_BASE, tests / CRITERIA_BASE.name)

    # Reproduce the grader's environment by *subtraction*, not by rebuilding
    # `sys.path`. The first attempt kept only site-packages and lost the
    # standard library with it, so the probe failed on `import pathlib` and
    # said nothing about the defect it was written for. Dropping PYTHONPATH
    # and running from the task's own directory is the whole difference
    # between this repo's layout and a bare staged task.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    # The grading decorator lives in the container, not here, so without a
    # stand-in this probe fails on every build for a reason that has nothing
    # to do with what it checks -- and a gate that always fails gets deleted
    # rather than heeded. The shim is *appended* to the path, so a real
    # installation always wins.
    shim = Path(tempfile.mkdtemp(prefix="grading-probe-"))
    (shim / "rewardkit.py").write_text(
        "def criterion(*a, **k):\n"
        "    def wrap(fn):\n"
        "        return fn\n"
        "    return wrap if not (a and callable(a[0])) else a[0]\n"
    )
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util, sys;"
            "sys.path.append(sys.argv[1]);"
            "spec = importlib.util.spec_from_file_location('criteria', 'criteria.py');"
            "m = importlib.util.module_from_spec(spec);"
            "spec.loader.exec_module(m)",
            str(shim),
        ],
        capture_output=True,
        text=True,
        cwd=tests,
        env=env,
    )
    shutil.rmtree(shim, ignore_errors=True)
    if probe.returncode:
        raise SystemExit(
            f"{name}: tests/criteria.py does not import from a bare task "
            f"directory, which is the only path the grader has. Every "
            f"criterion would fail to load and the task would score zero "
            f"for reasons no model can fix.\n{probe.stderr.strip()[-600:]}"
        )
    print(f"{name}: grading module ships and imports standalone")


def _refuse_while_a_sweep_is_reading(tasks: list[str]) -> None:
    """Refuse to rebuild a task some rollout is measuring right now.

    Harbor grades a trial when the trial finishes, against whatever
    `tests/oracle.json` says at that moment -- not against the key that was
    there when the agent started. Rebuilding mid-sweep therefore grades an
    answer to the OLD brief with the NEW key, and nothing anywhere reports
    it as anything but a low score.

    It cost a real measurement. A kimi trial on
    `commitment-revision-register` returned 26 rows and a superseded count
    of 127 against a true 128 -- a good answer by any reading -- and scored
    0.200, the empty-register floor, because `first_due` had been added to
    the key while it was still running. Its own instruction never mentioned
    the field.

    This is the same rule the rollout skill states from the other side:
    measure one version of the task. The reader cannot check it after the
    fact, because a contaminated trial is indistinguishable from a bad one.
    """

    try:
        running = subprocess.run(
            ["ps", "-eo", "command"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return
    # Only an actual rollout process, never a shell that happens to mention
    # one. This matched its own invocation: a single compound command that
    # ran `pkill -f scripts/rollout.py` and then the build appears in `ps`
    # as ONE line carrying both "rollout.py" and "--task <name>", so the
    # guard refused every build issued that way and reported four sweeps
    # that were not running.
    #
    # A shell wrapper is `/bin/zsh -c ...`; a rollout is a python process
    # whose script argument is the rollout itself. Requiring the two tokens
    # to sit next to each other -- `rollout.py` ... `--task <name>` with no
    # intervening `-c` -- is not enough, because a shell line contains them
    # in that order too. The interpreter is what separates them.
    busy = []
    for line in running.splitlines():
        head = line.split()[:2]
        if not any("python" in part for part in head):
            continue
        if "rollout.py" not in line:
            continue
        # The DATASET as well as the task. Two datasets here carry a task
        # of the same name -- `blocker-register` exists on both worlds --
        # and matching the task alone refused a build on one world because
        # a sweep was reading the other.
        if f"--dataset {DATASET}" not in line:
            continue
        busy.extend(task for task in tasks or [] if f"--task {task}" in line)
    if busy:
        raise SystemExit(
            "refusing to rebuild while a sweep is reading: "
            + ", ".join(sorted(set(busy)))
            + "\nHarbor grades each trial against the oracle as it stands when "
            "that trial\nfinishes, so rebuilding now grades answers to the old "
            "brief with the new key.\nStop the sweep, or wait for it, then build."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--refresh-truth", action="store_true")
    parser.add_argument(
        "--allow-band-absence",
        action="store_true",
        help=(
            "build a world that has none of something a firm certainly "
            "has. For a world recorded before the engine could produce "
            "it -- to exercise the harness against, never to ship."
        ),
    )
    args = parser.parse_args(argv)
    _refuse_while_a_sweep_is_reading(args.task)
    return build(args.log, args.task, args.refresh_truth, args.allow_band_absence)


if __name__ == "__main__":
    raise SystemExit(main())

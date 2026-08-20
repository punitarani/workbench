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
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from analysis import attempted_work
from analysis.artifact_mix import MixFloors, measure, violations
from analysis.coherence import MISBOOKED_LIMIT, check
from analysis.reachability import unreachable
from analysis.world_facts import load_world
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
SHARED_BUNDLE = REPO / "out" / "merrick" / "bundle"
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
    else REPO / "out" / "merrick" / "epoch" / "world.jsonl"
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


def build(world_log: Path, names: list[str], refresh: bool) -> int:
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
        subprocess.run(
            [sys.executable, str(solver), str(produced)],
            check=True,
            env={
                "WORKBENCH_STATE": str(SHARED_BUNDLE / "state"),
                # The working papers are files, not a surface. A solver
                # that grades them needs the same folder the agent gets.
                "WORKBENCH_WORKSPACE": str(SHARED_BUNDLE / "workspace"),
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            },
        )
        answer = json.loads(produced.read_text())
        produced.unlink()
        oracle_path = task / "tests" / "oracle.json"
        if refresh or not oracle_path.exists():
            oracle_path.parent.mkdir(parents=True, exist_ok=True)
            oracle_path.write_text(json.dumps(answer, indent=1) + "\n")
            print(f"{name}: oracle written")
        elif json.loads(oracle_path.read_text()) != answer:
            raise SystemExit(
                f"{name}: the reference solver no longer reproduces its oracle. "
                "Rebuild the world or pass --refresh-truth deliberately."
            )
        else:
            print(f"{name}: oracle verified")

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

        _ship_grading_base(task, name)

        bundle = task / "bundle"
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.copytree(SHARED_BUNDLE, bundle)
        staged = stage(bundle, task / "environment", repo_root=REPO)
        print(f"{name}: staged -> {staged}")
    return 0


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
    if not (tests / "criteria.py").is_file():
        return
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--refresh-truth", action="store_true")
    args = parser.parse_args(argv)
    return build(args.log, args.task, args.refresh_truth)


if __name__ == "__main__":
    raise SystemExit(main())

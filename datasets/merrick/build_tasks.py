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
from pathlib import Path

from analysis import attempted_work
from analysis.artifact_mix import MixFloors, measure, violations
from analysis.coherence import MISBOOKED_LIMIT, check
from analysis.reachability import unreachable
from analysis.world_facts import load_world
from core.worldlog import read_events
from environment.materialize import materialize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hartwell"))

from harbor_stage import stage  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
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
        distinct_paths=len({d.path for d in facts.documents.values()}),
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

    available = sorted(p.name for p in TASKS.iterdir() if p.is_dir())
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

        bundle = task / "bundle"
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.copytree(SHARED_BUNDLE, bundle)
        staged = stage(bundle, task / "environment", repo_root=REPO)
        print(f"{name}: staged -> {staged}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--refresh-truth", action="store_true")
    args = parser.parse_args(argv)
    return build(args.log, args.task, args.refresh_truth)


if __name__ == "__main__":
    raise SystemExit(main())

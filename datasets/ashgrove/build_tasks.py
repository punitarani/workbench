"""Build Ashgrove task environments from its world log.

    uv run python datasets/ashgrove/build_tasks.py [--task NAME ...]

Materializes one seatless bundle from the epoch log and stages it for
every task under ``tasks/`` — seatless because these are firm-wide audits
that read across seats, the same choice the Hartwell tasks make. Each
task's reference solver runs against the fresh bundle and its output must
match the committed oracle byte for byte; ``--refresh-truth`` is the only
way to move that line, and it is a deliberate act.
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

from workbench.analysis.coherence import MISBOOKED_LIMIT, check
from workbench.analysis.reachability import unreachable
from workbench.analysis.world_facts import load_world
from workbench.environment.materialize import materialize
from workbench.environment.snapshot import write_tracker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hartwell"))

from harbor_stage import stage  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
DEFAULT_LOG = REPO / "out" / "ashgrove" / "epoch" / "world.jsonl"
SHARED_BUNDLE = REPO / "out" / "ashgrove" / "bundle"
# Day four of a fifteen-day world: late enough that every engagement has
# moved and hours are on the board, early enough that most of them move
# again afterwards. Measured at this cutoff the sheet carries 133 effort
# lines, 116 of which have since drifted, and misses 13 pairs that only
# started later.
TRACKER_CUTOFF = 4 * 86_400
TRACKER_NAME = "engagement-tracker-week1.md"


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


def _as_of(facts, cutoff: int) -> str:
    """The snapshot day as a calendar date, read off the world's own epoch."""

    epoch = datetime.datetime.fromisoformat(facts.epoch)
    return (epoch + datetime.timedelta(seconds=cutoff)).date().isoformat()


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

    env = materialize(world_log, SHARED_BUNDLE, seat=None)
    print(f"materialized {env.event_count} events -> {SHARED_BUNDLE}")

    # A tracker somebody typed up partway through, left in the shared drive
    # the way a real one is. It is a true statement about its own day and a
    # false one about now, which is the point: reconciling it is one
    # judgement that moves every row, and that is the only thing measured
    # so far that moves a frontier model's score at all.
    tracker = write_tracker(facts, TRACKER_CUTOFF, _as_of(facts, TRACKER_CUTOFF))
    tracker_path = SHARED_BUNDLE / "workspace" / "admin" / TRACKER_NAME
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    tracker_path.write_text(tracker)
    print(f"tracker written -> {tracker_path.relative_to(SHARED_BUNDLE)}")
    # Which world this bundle is. Everything downstream -- the independence
    # check, the miss classifier -- needs the log the oracles were computed
    # from, and defaulting to a fixed path meant comparing a fresh oracle
    # against a stale world and reporting 256 disagreements that were only
    # a wrong filename.
    (SHARED_BUNDLE / "SOURCE").write_text(str(world_log.resolve()) + "\n")
    if env.skipped_renders:
        for skip in env.skipped_renders:
            print(f"  render skipped: {skip}")

    selected = names or sorted(p.name for p in TASKS.iterdir() if p.is_dir())
    for name in selected:
        task = TASKS / name
        solver = task / "solution" / "solve.py"
        if not solver.exists():
            print(f"{name}: no reference solver; skipping")
            continue
        produced = SHARED_BUNDLE / "workspace" / f"{name}-answer.json"
        subprocess.run(
            [sys.executable, str(solver), str(produced)],
            check=True,
            env={
                "WORKBENCH_STATE": str(SHARED_BUNDLE / "state"),
                "PATH": "/usr/bin:/bin",
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
        missing = unreachable(answer, SHARED_BUNDLE / "state")
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

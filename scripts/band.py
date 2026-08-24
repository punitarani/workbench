"""The three-model mean per task, and whether it is real.

    uv run python scripts/band.py --dataset <name>
    uv run python scripts/band.py --dataset <name> --tag-opus fair-k3

The target is a task whose score, averaged over gpt-5.6-sol, Opus 5 and
glm-5.2, lands in 0.2-0.8. Averaging invites one specific way of cheating
yourself, so this refuses it:

**A DNF is not a zero.** A model that ran out of clock, or ended its turn
believing sub-agents were still working, or never wrote the deliverable at
all, has not scored 0.000 -- it has not scored. Averaged in as a zero it
drags any task into the band: Opus 1.000 + Sol 0.600 + glm *nothing*
reads as 0.533, which looks like a well-calibrated task and is really a
broken measurement wearing one's clothes.

**But a DNF is not a disqualification either.** How well a model answers
and how often it manages to answer at all are different facts, and
collapsing them in either direction loses one of them. gpt-5.6-sol on
`approval-register`: 47 steps and 0.997 on one trial, 5 and 7 steps and
no deliverable on the other two. The task is plainly solvable by it, and
a rule that discards the 0.997 because it is outnumbered reports nothing
at all about a model that nearly aced the work.

So the score is the mean over **gradeable trials only**, at least two of
them so it is never a single sample, and the completion rate is printed
beside it rather than folded into it. Below two, the task is reported
loudly as incomplete -- with the reason, because "glm timed out" and
"glm answered badly" call for opposite fixes.
"""

import argparse
import ast
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JOBS = REPO / "jobs"
DATASETS = REPO / "datasets"

# Two, not a majority. One gradeable trial is an anecdote; two is an
# estimate. Requiring a majority threw away a 0.997 on a task the model
# demonstrably solves, because its other two attempts ended in an
# orchestration failure that says nothing about the task.
_MIN_GRADEABLE = 2

# The three the goal names, in the order a report should read.
# The sign-off trio for merrick: a frontier tier, a strong mid tier, and
# an open-weights tier, so a band is read across capability rather than
# across one vendor. glm-5.2 stays routable as a fallback.
MODELS = ("gpt-5.6-sol", "opus-5", "glm-5.2", "kimi-k3")

# The short prefix each model's job tags carry. Shared with the rollout
# writer, because a writer and a reader that disagree about a job name
# fail silently -- the sweep runs, the scores land, and this reports "not
# run", which is indistinguishable from never having measured.
TAG_PREFIX = {
    "gpt-5.6-sol": "gpt",
    "opus-5": "opus",
    "glm-5.2": "glm",
    "kimi-k3": "kimi",
}


# Several tags per model, newest first: the k=9 re-samples live under their
# own, and a world's scores must never be read beside another's. Requiring
# the reader to remember which tag holds the best evidence is how a task
# that *is* in band gets reported as 0 in band -- which happened, on the
# first one that qualified.
#
# `-v7-` is the merrick run on the oracle whose eleven bad rows were the
# score; `-v8-` the one whose three were; `-v9-` the corrected task. They
# are listed newest first and never merged: a run against a different
# oracle is a different measurement.
#
# Module level, not a local inside `main`, because the test that checks a
# sweep writes a tag the aggregator searches used to keep its OWN copy of
# this table. A hand-kept copy of the thing under test cannot fail for the
# right reason -- it only fails when it goes stale, which is how adding a
# fourth tier broke it.
# `<prefix>-k9` is on every row because that is what `rollout.py` writes
# when nobody passes `--tag`, and a default sweep whose scores the default
# reader cannot find is the exact failure this table exists to prevent.
DEFAULT_TAGS: dict[str, list[str]] = {
    "gpt-5.6-sol": ["gpt-v9-k3", "gpt-v8-k3", "gpt-v7-k3", "gpt-k9", "gpt-k3"],
    "opus-5": ["opus-v9-k3", "opus-v8-k3", "opus-v7-k3", "opus-k9", "fair-k3"],
    "glm-5.2": ["glm-v9-k3", "glm-v8-k3", "glm-v7-k3", "glm-k9", "glm-fair"],
    "kimi-k3": ["kimi-v9-k3", "kimi-v8-k3", "kimi-v7-k3", "kimi-k9"],
}


def _trials(job: Path) -> list[Path]:
    if not job.is_dir():
        return []
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _retired(task: Path) -> bool:
    """Whether this task was withdrawn on measured evidence.

    Three of this dataset's tasks were retired and simply left in place,
    which was invisible: they carry a full `task.toml`, an instruction and
    a solver, and differ from a live task only in never having been built.
    A reader that iterates the directory cannot tell them apart, so it
    either reports tasks nobody intends to run or -- once it began
    refusing tasks whose deliverable it cannot name -- stops on one.
    """

    manifest = task / "task.toml"
    if not manifest.is_file():
        return False
    return any(
        line.split("#", 1)[0].replace(" ", "").startswith("retired=true")
        for line in manifest.read_text(encoding="utf-8").splitlines()
    )


class UnknownDeliverable(SystemExit):
    """The reader cannot tell what file the task asked for."""


def _deliverable(tasks_dir: Path, task: str) -> str:
    """The file this task asks the agent to write.

    Read from the task's own `criteria.py`, which is where the name lives.
    This looked for a line starting with `D =` in `grade.py`, and
    `grade.py` declares `DELIVERABLE = criteria.DELIVERABLE` -- so it
    returned None for every task in the dataset.

    That mattered because of how the caller used it. `_outcome` guarded
    its DNF check with `if wanted and ...`, so a None turned the check
    off: a trial that wrote no deliverable at all fell through to
    `reward.json`, which `test.sh` writes as 0.0 whatever happened. Every
    did-not-finish was being averaged in as a **zero** -- which is the
    precise failure this module's own docstring exists to prevent, and it
    fails in the flattering direction, dragging any task toward the band.

    Raising rather than returning None is the other half of the fix. A
    reader that cannot tell what the task asked for must stop, not quietly
    grade as though every trial answered.
    """

    criteria = tasks_dir / task / "tests" / "criteria.py"
    if not criteria.is_file():
        raise UnknownDeliverable(
            f"{task}: no tests/criteria.py, so there is no way to tell "
            "whether a trial produced an answer or nothing at all."
        )
    tree = ast.parse(criteria.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "DELIVERABLE":
                value = ast.literal_eval(node.value)
                if isinstance(value, str) and value:
                    return value
    raise UnknownDeliverable(
        f"{task}: tests/criteria.py names no DELIVERABLE. Without it a "
        "trial that wrote nothing is indistinguishable from one that "
        "answered badly, and the two average differently."
    )


def _outcome(trial: Path, wanted: str) -> tuple[float | None, str]:
    """The trial's score, or None with the reason it is not one."""

    verifier = trial / "verifier"
    # A timeout is only a DNF when nothing was written. If the deliverable
    # is there and the grader scored it, the trial answered -- and the
    # score is what the model produced inside its budget, which is the
    # thing being measured.
    #
    # This was the other way round, and it mattered: on
    # opening-days-commitment-register the two timed-out trials scored
    # 0.720 and 0.770 against a 0.655 average for the rest. A truncated
    # write scores low, not high; those were finished answers whose
    # harness ran out of clock afterwards. Discarding them moved the task
    # from 0.802 to 0.795 and across the band boundary, which is a good
    # reason to get the rule right rather than to keep the one that
    # flattered the result.
    if not (verifier / f"submitted-{wanted}").is_file():
        # Working files may be present; the answer is not.
        exception = trial / "exception.txt"
        if exception.is_file() and "AgentTimeoutError" in exception.read_text():
            return None, "timeout, nothing written"
        return None, "no deliverable"
    reward = verifier / "reward.json"
    if not reward.is_file():
        return None, "no reward"
    try:
        return float(json.loads(reward.read_text())["reward"]), "ok"
    except ValueError, KeyError, TypeError:
        return None, "unreadable reward"


def measure(tasks_dir: Path, task: str, job: Path) -> dict:
    trials = _trials(job)
    wanted = _deliverable(tasks_dir, task)
    scores, reasons = [], []
    for trial in trials:
        value, why = _outcome(trial, wanted)
        (scores if value is not None else reasons).append(
            value if value is not None else why
        )
    return {
        "trials": len(trials),
        "scored": len(scores),
        "mean": statistics.fmean(scores) if scores else None,
        "min": min(scores) if scores else None,
        "max": max(scores) if scores else None,
        "excluded": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        required=True,
        help="dataset name under datasets/; job names are <dataset>-<task>-<tag>",
    )
    # One flag per model, derived from MODELS rather than written out, so
    # adding a tier cannot leave a column with no way to name its tag --
    # which is how kimi-k3's first sweep read as "not run" while three
    # graded trials sat on disk.
    for _model in MODELS:
        parser.add_argument(
            f"--tag-{TAG_PREFIX[_model]}", action="append", default=None
        )
    args = parser.parse_args(argv)
    tasks_dir = DATASETS / args.dataset / "tasks"
    if not tasks_dir.is_dir():
        parser.error(f"no tasks under {tasks_dir}")
    tags = {
        model: getattr(args, f"tag_{TAG_PREFIX[model]}") or DEFAULT_TAGS[model]
        for model in MODELS
    }

    header = "".join(f"{model:>13s}" for model in MODELS)
    print(f"{'task':32s}{header} {'mean':>7s}  verdict")
    print("-" * 92)
    in_band = []
    for task in sorted(p.name for p in tasks_dir.iterdir() if p.is_dir()):
        # `_template` is a scaffold, not a task: it has no DELIVERABLE, so
        # reading it raises UnknownDeliverable -- a SystemExit, which took
        # the whole report down and printed a header with no rows under it.
        # A leading underscore is this tree's mark for "not a task".
        if task.startswith("_"):
            continue
        if _retired(tasks_dir / task):
            continue
        cells, means, blocked, rates = [], [], [], []
        for model in MODELS:
            # Best evidence wins: the job with the most gradeable trials,
            # and the larger sample breaks a tie.
            candidates = [
                measure(tasks_dir, task, JOBS / f"{args.dataset}-{task}-{tag}")
                for tag in tags[model]
            ]
            found = max(
                candidates,
                key=lambda c: (c["scored"], c["trials"]),
            )
            if found["mean"] is None:
                cells.append("  --")
                why = found["excluded"][0] if found["excluded"] else "not run"
                blocked.append(f"{model}: {why}")
            else:
                cells.append(f"{found['mean']:.3f}")
                means.append(found["mean"])
                if found["scored"] < _MIN_GRADEABLE:
                    blocked.append(
                        f"{model}: only {found['scored']}/{found['trials']} gradeable"
                    )
                elif found["scored"] < found["trials"]:
                    # Reported, never averaged in: the score stands on the
                    # trials that produced an answer, and the reader is told
                    # how many did.
                    rates.append(
                        f"{model} answered {found['scored']}/{found['trials']}"
                    )
        if rates and not blocked:
            note = "  (" + "; ".join(rates) + ")"
        else:
            note = ""
        if blocked:
            verdict = "INCOMPLETE — " + "; ".join(blocked)
            mean_text = "     --"
        else:
            mean = statistics.fmean(means)
            mean_text = f"{mean:7.3f}"
            if 0.2 <= mean <= 0.8:
                verdict = "IN BAND"
                in_band.append((task, mean))
            else:
                verdict = "out of band"
        print(
            f"{task:32s} {cells[0]:>13s} {cells[1]:>10s} {cells[2]:>10s}"
            f" {mean_text}  {verdict}{note}"
        )

    print(f"\n{len(in_band)} task(s) in 0.2-0.8 on the three-model mean")
    for task, mean in sorted(in_band, key=lambda kv: kv[1]):
        print(f"    {mean:.3f}  {task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

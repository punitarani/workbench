"""The three-model mean per task, and whether it is real.

    uv run python datasets/ashgrove/band.py
    uv run python datasets/ashgrove/band.py --tag-opus fair-k3 --tag-glm glm-fair

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
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOBS = REPO / "jobs"
TASKS = Path(__file__).resolve().parent / "tasks"

# Two, not a majority. One gradeable trial is an anecdote; two is an
# estimate. Requiring a majority threw away a 0.997 on a task the model
# demonstrably solves, because its other two attempts ended in an
# orchestration failure that says nothing about the task.
_MIN_GRADEABLE = 2

# The three the goal names, in the order a report should read.
MODELS = ("gpt-5.6-sol", "opus-5", "glm-5.2")


def _trials(job: Path) -> list[Path]:
    if not job.is_dir():
        return []
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _deliverable(task: str) -> str | None:
    grade = TASKS / task / "tests" / "answer" / "grade.py"
    if not grade.is_file():
        return None
    for line in grade.read_text().splitlines():
        if line.startswith("D ="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None


def _outcome(trial: Path, wanted: str | None) -> tuple[float | None, str]:
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
    if wanted and not (verifier / f"submitted-{wanted}").is_file():
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


def measure(task: str, job: Path) -> dict:
    trials = _trials(job)
    wanted = _deliverable(task)
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
    parser.add_argument("--tag-gpt", action="append", default=None)
    parser.add_argument("--tag-opus", action="append", default=None)
    parser.add_argument("--tag-glm", action="append", default=None)
    args = parser.parse_args(argv)
    # Several tags per model, because the k=9 re-samples live under their
    # own. Requiring the reader to remember which tag holds the best
    # evidence is how a task that *is* in band gets reported as 0 in band
    # -- which happened, on the first one that qualified.
    tags = {
        "gpt-5.6-sol": args.tag_gpt or ["gpt-k9", "gpt-k3"],
        "opus-5": args.tag_opus or ["fair-k3"],
        "glm-5.2": args.tag_glm or ["glm-k9", "glm-fair"],
    }

    print(
        f"{'task':32s} {'gpt-5.6-sol':>13s} {'opus-5':>10s} {'glm-5.2':>10s}"
        f" {'mean':>7s}  verdict"
    )
    print("-" * 92)
    in_band = []
    for task in sorted(p.name for p in TASKS.iterdir() if p.is_dir()):
        cells, means, blocked, rates = [], [], [], []
        for model in MODELS:
            # Best evidence wins: the job with the most gradeable trials,
            # and the larger sample breaks a tie.
            candidates = [
                measure(task, JOBS / f"ashgrove-{task}-{tag}") for tag in tags[model]
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

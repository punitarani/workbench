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

So a task's mean counts only when every model produced a gradeable
answer in a majority of its trials. Everything else is reported, loudly,
as incomplete -- with the reason, because "glm timed out" and "glm
answered badly" call for opposite fixes.
"""

import argparse
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOBS = REPO / "jobs"
TASKS = Path(__file__).resolve().parent / "tasks"

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

    if (trial / "exception.txt").is_file():
        text = (trial / "exception.txt").read_text()
        if "AgentTimeoutError" in text:
            return None, "timeout"
    verifier = trial / "verifier"
    if wanted and not (verifier / f"submitted-{wanted}").is_file():
        # Working files may be present; the answer is not.
        return None, "no deliverable"
    reward = verifier / "reward.json"
    if not reward.is_file():
        return None, "no reward"
    try:
        return float(json.loads(reward.read_text())["reward"]), "ok"
    except (ValueError, KeyError, TypeError):
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
    parser.add_argument("--tag-gpt", default="gpt-k3")
    parser.add_argument("--tag-opus", default="fair-k3")
    parser.add_argument("--tag-glm", default="glm-fair")
    args = parser.parse_args(argv)
    tags = {
        "gpt-5.6-sol": args.tag_gpt,
        "opus-5": args.tag_opus,
        "glm-5.2": args.tag_glm,
    }

    print(f"{'task':32s} {'gpt-5.6-sol':>13s} {'opus-5':>10s} {'glm-5.2':>10s}"
          f" {'mean':>7s}  verdict")
    print("-" * 92)
    in_band = []
    for task in sorted(p.name for p in TASKS.iterdir() if p.is_dir()):
        cells, means, blocked = [], [], []
        for model in MODELS:
            found = measure(task, JOBS / f"ashgrove-{task}-{tags[model]}")
            if found["mean"] is None:
                cells.append("  --")
                why = found["excluded"][0] if found["excluded"] else "not run"
                blocked.append(f"{model}: {why}")
            else:
                cells.append(f"{found['mean']:.3f}")
                means.append(found["mean"])
                # A majority of trials must be gradeable, or the mean is
                # taken over whichever ones happened to survive.
                if found["scored"] * 2 <= found["trials"]:
                    blocked.append(
                        f"{model}: only {found['scored']}/{found['trials']} gradeable"
                    )
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
        print(f"{task:32s} {cells[0]:>13s} {cells[1]:>10s} {cells[2]:>10s}"
              f" {mean_text}  {verdict}")

    print(f"\n{len(in_band)} task(s) in 0.2-0.8 on the three-model mean")
    for task, mean in sorted(in_band, key=lambda kv: kv[1]):
        print(f"    {mean:.3f}  {task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

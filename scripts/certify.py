"""Decide whether a task is finished, by checks rather than by opinion.

    uv run python scripts/certify.py --dataset merrick \
        --task live-commitment-register --tag opus-v10-k3 --tag glm-v10-k3 \
        --tag kimi-v10-k3

Four things have to hold at once, and every one of them has been wrong on a
task that looked finished:

**1. Built, and by two derivations.** `tests/oracle.json` exists and
`checks/verify.py` re-derives it. The build enforces this; this restates it
so a task cannot be certified from scores alone.

**2. The floors leave room.** An answer that reports every candidate must
not reach the band. A register once paid a dump 0.624 -- only 0.376 of the
scale sat above a reader who never comprehended anything -- and the number
that drives it is the candidate ratio, not the row count.

**3. The band, on at least three tiers.** Every tier's mean inside
0.2-0.8, each from at least three trials that produced an answer. A DNF is
excluded rather than averaged as a zero: how well a model answers and how
often it manages to answer are different facts, and folding one into the
other puts any task in any band you like.

**4. No row declined by every trial.** This is the one that is not about
scores. Genuine model error is stochastic; two runs drop overlapping but
different rows. When every trial of every tier declines the SAME row, the
key is the thing they have in common -- and on the one task certified in
band before this check existed, there were four such rows, two of which
were defects. A row may only survive here once `adjudicate.py` has been run
over it and a reader has admitted it, which this file records as a waiver
naming the row.

The exit code is the verdict: 0 certified, 1 not. Nothing here is a
judgement call left to the reader, which is the point -- "done" was an
opinion, and opinions had certified a register with eleven bad rows.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

BAND = (0.2, 0.8)
MIN_TIERS = 3
MIN_TRIALS = 3
# From `datasets/*/baselines.py`; restated so a drifting copy is visible as
# a disagreement rather than as a silently different verdict.
DUMP_CEILING = 0.8


def _rewards(job: Path, task: str) -> list[float]:
    if not job.is_dir():
        return []
    found = []
    for trial in sorted(job.iterdir()):
        if trial.name.rsplit("__", 1)[0] != task and (trial / "verifier").is_dir():
            continue
        reward = trial / "verifier" / "reward.json"
        if not reward.is_file():
            continue
        try:
            found.append(float(json.loads(reward.read_text())["reward"]))
        except ValueError, KeyError, TypeError:
            continue
    return found


def check_sweeps_are_current(
    dataset: str, task: str, task_dir: Path, tags: list[str], problems: list[str]
) -> None:
    """Refuse a band measured against a key that has since changed.

    Nothing errors when this happens. The scores are real, the trials
    completed, the table prints -- and every number in it was earned
    against a different answer key. Only a timestamp catches it.

    It caught this file's own first run: `live-commitment-register` was
    certified on three sweeps taken before the same day's oracle fix, which
    moved a row's date. Two of the three tiers would very likely still be in
    band, and that is exactly the problem -- "very likely" is not a
    measurement.
    """

    oracle = task_dir / "tests" / "oracle.json"
    if not oracle.is_file():
        return
    written = oracle.stat().st_mtime
    for tag in tags:
        job = REPO / "jobs" / f"{dataset}-{task}-{tag}"
        if not job.is_dir():
            continue
        trials = [p for p in job.iterdir() if (p / "verifier").is_dir()]
        if not trials:
            continue
        ran = max(p.stat().st_mtime for p in trials)
        if ran < written:
            problems.append(
                f"{tag}: ran before the current oracle was written, so its "
                "scores were earned against a superseded key. Re-run it"
            )


def check_built(task_dir: Path, problems: list[str]) -> None:
    for what, where in (
        ("oracle", task_dir / "tests" / "oracle.json"),
        ("grading criteria", task_dir / "tests" / "criteria.py"),
        ("independent verifier", task_dir / "checks" / "verify.py"),
        ("reference solver", task_dir / "solution" / "solve.py"),
        ("staged environment", task_dir / "environment"),
    ):
        if not where.exists():
            problems.append(f"not built: no {what} at {where.name}")


def check_floors(dataset: str, task_dir: Path, problems: list[str]) -> None:
    """Re-measure rather than trust the build log, which is not kept."""

    sys.path.insert(0, str(REPO / "datasets" / dataset))
    try:
        import baselines  # type: ignore[import-not-found]
    except ImportError:
        problems.append(f"{dataset}: no baselines module, so no floor to check")
        return
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    floors = baselines.measure(task_dir, oracle)
    if not floors:
        problems.append(
            "no floors could be measured. Without them a score cannot be "
            "read at all: 0.5 may be comprehension or may be what the task "
            "pays for reporting everything"
        )
        return
    dump = floors.get("reported_every_candidate")
    if dump is None:
        problems.append(
            "no dump floor: the task states no count of what was read, so "
            "the strongest no-comprehension strategy is unmeasurable"
        )
    elif dump >= DUMP_CEILING:
        problems.append(
            f"a dump scores {dump:.3f}, at or above the {DUMP_CEILING} top of "
            "the band; every score sits on top of it"
        )
    print(f"  floors: {', '.join(f'{k} {v:.3f}' for k, v in sorted(floors.items()))}")


def check_band(
    dataset: str, task: str, tags: list[str], problems: list[str]
) -> dict[str, float]:
    means: dict[str, float] = {}
    for tag in tags:
        job = REPO / "jobs" / f"{dataset}-{task}-{tag}"
        rewards = _rewards(job, task)
        if len(rewards) < MIN_TRIALS:
            problems.append(
                f"{tag}: {len(rewards)} graded trial(s), fewer than {MIN_TRIALS}. "
                "Three samples of a noisy outcome cannot separate one-in-three "
                "from one-in-nine"
            )
            continue
        mean = sum(rewards) / len(rewards)
        means[tag] = mean
        inside = BAND[0] <= mean <= BAND[1]
        print(
            f"  {tag:16s} {sorted(round(r, 3) for r in rewards)}  mean {mean:.3f}"
            f"  {'in band' if inside else 'OUT OF BAND'}"
        )
        if not inside:
            problems.append(f"{tag}: mean {mean:.3f} is outside {BAND[0]}-{BAND[1]}")
    if len(means) < MIN_TIERS:
        problems.append(
            f"{len(means)} tier(s) measured, fewer than {MIN_TIERS}. A band on "
            "one tier is a fact about that tier"
        )
    return means


def check_no_unanimous_refusals(
    dataset: str, task: str, tags: list[str], waived: set[str], problems: list[str]
) -> None:
    """Rows every trial declined, which is a claim about the key."""

    command = [
        sys.executable,
        str(REPO / "scripts" / "diagnose.py"),
        "--dataset",
        dataset,
        "--task",
        task,
    ]
    for tag in tags:
        command += ["--tag", tag]
    done = subprocess.run(command, capture_output=True, text=True)
    declined = [
        line.split("  ", 2)[-1].split("  <==")[0].strip()
        for line in done.stdout.splitlines()
        if "<== EVERY trial" in line
    ]
    contested = _contested(done.stdout)
    unwaived = [row for row in declined if row not in waived]
    for row in unwaived:
        rival = contested.get(row)
        if rival:
            problems.append(
                f"every trial declined {row!r}, and {rival[1]} of them answered "
                f"{rival[0]!r} for the same key. That is a disagreement about "
                "the VALUE, not a row they missed. Adjudicate the key's passage "
                "TOGETHER with the passage behind their value: a judge shown "
                "only the key's own evidence can confirm that passage and leave "
                "the row wrong anyway, because what makes it wrong is elsewhere"
            )
            continue
        problems.append(
            f"every trial declined {row!r}. Adjudicate it against the source "
            "with scripts/adjudicate.py; if a reader admits it, waive it here "
            "with --waive"
        )
    if declined and not unwaived:
        print(f"  {len(declined)} row(s) declined by every trial, all waived")


# At or above this, a criterion is solved rather than measured.
SOLVED = 0.99


def check_heaviest_criterion(
    dataset: str, task: str, tags: list[str], problems: list[str]
) -> None:
    """Refuse a task whose SUBSTANTIVE criterion is at ceiling for some tier.

    A headline score inside the band can be made entirely of bookkeeping.
    `live-commitment-register` measured 0.909 for the strongest tier with
    every one of its fourteen rows correct in every trial: `live.f1` 1.000,
    `row_facts` 1.000, and one integer -- the count of what was discarded --
    wrong by one. Eight of the eleven weight was solved. Read as a band,
    0.909 says "hard"; read per criterion it says the extraction is over
    and what remains is arithmetic on the part nobody can see in the
    deliverable.

    So the check is on the heaviest criterion rather than the mean. A task
    can only claim to measure what its weight is actually spent on.
    """

    for tag in tags:
        job = REPO / "jobs" / f"{dataset}-{task}-{tag}"
        if not job.is_dir():
            continue
        totals: dict[str, list[float]] = {}
        weights: dict[str, float] = {}
        for trial in sorted(job.iterdir()):
            details = trial / "verifier" / "reward-details.json"
            if not details.is_file():
                continue
            try:
                criteria = json.loads(details.read_text())["answer"]["criteria"]
            except ValueError, KeyError, TypeError:
                continue
            for item in criteria:
                totals.setdefault(item["name"], []).append(float(item["value"]))
                weights[item["name"]] = float(item.get("weight", 1.0))
        if not totals:
            continue
        heaviest = max(weights, key=lambda name: weights[name])
        scores = totals[heaviest]
        mean = sum(scores) / len(scores)
        share = weights[heaviest] / sum(weights.values())
        print(
            f"  {tag:16s} heaviest criterion {heaviest!r} "
            f"({share:.0%} of the weight) mean {mean:.3f}"
        )
        if mean >= SOLVED:
            problems.append(
                f"{tag}: {heaviest!r} carries {share:.0%} of the weight and "
                f"scores {mean:.3f}. The headline band is made of the "
                "remaining criteria, so this tier is not being measured on "
                "what the task is about"
            )


def _contested(report: str) -> dict[str, tuple[str, int]]:
    """Declined rows the trials answered at a DIFFERENT value, from diagnose.

    Read off the report rather than recomputed here. A second implementation
    of "which rows are contested" is a second thing to drift, and this one
    only has to name the rows the report already named.
    """

    found: dict[str, tuple[str, int]] = {}
    group = held = None
    for line in report.splitlines():
        stripped = line.strip()
        if " | " in stripped and not stripped.startswith(("declined", "invented")):
            group, held = stripped, None
        elif stripped.startswith("key ") and "declined by" in stripped:
            held = stripped.split("'")[1] if "'" in stripped else None
        elif stripped.startswith("trials ") and "produced by" in stripped and group:
            if held is None:
                continue
            value = stripped.split("'")[1]
            count = int(stripped.split("produced by ")[1].split(" ")[0])
            row = f"{group} | {held}"
            if row not in found or count > found[row][1]:
                found[row] = (value, count)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--tag", action="append", default=[], required=True)
    parser.add_argument(
        "--waive",
        action="append",
        default=[],
        help="a row every trial declines that a reader has adjudicated as "
        "sound; name it exactly as diagnose.py prints it",
    )
    args = parser.parse_args(argv)

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    print(f"\n=== certifying {args.task} ===\n")
    problems: list[str] = []
    check_built(task_dir, problems)
    if problems:
        return _verdict(args.task, problems)
    check_sweeps_are_current(args.dataset, args.task, task_dir, args.tag, problems)
    check_floors(args.dataset, task_dir, problems)
    check_band(args.dataset, args.task, args.tag, problems)
    check_heaviest_criterion(args.dataset, args.task, args.tag, problems)
    check_no_unanimous_refusals(
        args.dataset, args.task, args.tag, set(args.waive), problems
    )
    return _verdict(args.task, problems)


def _verdict(task: str, problems: list[str]) -> int:
    print()
    if problems:
        print(f"  NOT CERTIFIED — {len(problems)} problem(s):")
        for problem in problems:
            print(f"    - {problem}")
        return 1
    print(f"  {task}: CERTIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

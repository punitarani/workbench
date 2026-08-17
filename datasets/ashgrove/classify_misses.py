"""Why did that criterion miss — the model, the task, or the environment?

    uv run python datasets/ashgrove/classify_misses.py jobs/ashgrove-<task>-<tag>

Every score below 1.0 is a defect until proved otherwise. This prints the
evidence for proving it, one criterion at a time, so the verdict is read
off a diff instead of guessed from a number.

Three verdicts, and only one of them may ship:

**E — environment.** The fact is not reachable through the served tools, or
the record contradicts itself with no stated rule. Clio served no matter
history at all once, and Opus 5 scored 0.067 on an answer the tools could
not produce; that was read as a model failure for longer than it should
have been.

**T — task.** The instruction is ambiguous, the oracle is wrong, the
grader is wrong, or a tolerance is unfair. The firm's hours came to 817.23
from the entries and 817.27 from the rounded rows, the instruction named
neither, and an agent with all 197 rows right lost both totals on a coin
toss.

**M — model.** Reachable, unambiguous, oracle independently confirmed, and
the agent got it wrong anyway. This is the only kind of miss an RL
environment is allowed to be measuring.

What this can decide mechanically it decides: whether the oracle survives
an independent derivation, whether every value it names is served, and
exactly which rows and fields the agent got wrong. What it cannot decide —
whether the instruction was ambiguous — it hands to a person, with the
disagreement in front of them.
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"


def _trials(job: Path) -> list[Path]:
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _submitted(trial: Path) -> dict | None:
    """What the agent wrote, if the verifier kept it."""

    root = trial / "artifacts" / "logs" / "artifacts"
    for path in sorted(root.glob("*.json")) if root.is_dir() else ():
        try:
            loaded = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def _below_one(trial: Path) -> list[tuple[str, float]]:
    details = trial / "verifier" / "reward-details.json"
    if not details.is_file():
        return []
    out = []
    for dimension, block in json.loads(details.read_text()).items():
        if not isinstance(block, dict):
            continue
        for entry in block.get("criteria", []):
            value = float(entry.get("value") or 0.0)
            if value < 1.0:
                out.append((f"{dimension}.{entry['name']}", value))
    return out


def _row_key(row: dict, key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(k)).strip().casefold() for k in key)


def _diff_rows(mine: list, theirs: list, key: tuple[str, ...]) -> None:
    """Which rows are missing, invented, and wrong — with counts and samples."""

    want = {_row_key(r, key): r for r in theirs if isinstance(r, dict)}
    got = {_row_key(r, key): r for r in mine if isinstance(r, dict)}
    missing, invented = sorted(want.keys() - got), sorted(got.keys() - want)
    print(f"    rows: oracle {len(want)}, agent {len(got)}, "
          f"missing {len(missing)}, invented {len(invented)}")
    for label, rows in (("missing", missing), ("invented", invented)):
        for row in rows[:5]:
            print(f"      {label}: {row}")
        if len(rows) > 5:
            print(f"      {label}: ... and {len(rows) - 5} more")

    wrong: Counter[str] = Counter()
    samples: list[str] = []
    for shared in sorted(want.keys() & got.keys()):
        for field, expected in want[shared].items():
            if field in key:
                continue
            actual = got[shared].get(field)
            if str(actual).strip().casefold() != str(expected).strip().casefold():
                wrong[field] += 1
                if len(samples) < 6:
                    samples.append(
                        f"      {shared} {field}: agent {actual!r}, oracle {expected!r}"
                    )
    if wrong:
        print(f"    wrong fields on shared rows: {dict(wrong)}")
        for sample in samples:
            print(sample)


def classify(job: Path, task: str, key: tuple[str, ...] | None) -> int:
    trials = _trials(job)
    if not trials:
        print(f"{job}: no trials", file=sys.stderr)
        return 1

    oracle_path = TASKS / task / "tests" / "oracle.json"
    oracle = json.loads(oracle_path.read_text())
    rows_field = next(
        (k for k, v in oracle.items() if isinstance(v, list) and v), None
    )

    print(f"=== {job.name}: {len(trials)} trial(s), task {task}\n")

    # Whole-task evidence first: it is the same for every criterion, and it
    # is what decides E and T before any individual row is looked at.
    print("--- is the oracle independently confirmed? (T)")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "verify_oracle.py"),
         "--task", task],
        capture_output=True, text=True, cwd=REPO,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
    )
    for line in result.stdout.strip().splitlines()[1:]:
        print(f"    {line}")
    if result.returncode:
        print("    ^ the oracle and the log disagree: this is a T, not an M.")

    for trial in trials:
        misses = _below_one(trial)
        print(f"\n--- {trial.name}: {len(misses)} criterion(s) below 1.0")
        if not misses:
            continue
        for name, value in misses:
            print(f"    {name} = {value:.3f}")
        answer = _submitted(trial)
        if answer is None:
            print("    (the agent's answer was not preserved -- rerun with the "
                  "current test.sh, which copies it into /logs/artifacts)")
            continue
        for field, expected in oracle.items():
            if isinstance(expected, list):
                continue
            actual = answer.get(field)
            if str(actual).strip().casefold() != str(expected).strip().casefold():
                print(f"    {field}: agent {actual!r}, oracle {expected!r}")
        if rows_field and key:
            _diff_rows(answer.get(rows_field) or [], oracle[rows_field], key)

    print(
        "\nVerdict is yours. E if the evidence above shows the fact is not "
        "served or the record contradicts itself; T if the oracle failed its "
        "independent derivation or the instruction does not decide the case; "
        "M only when neither of those holds."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--task")
    parser.add_argument(
        "--key",
        help="comma-separated row key, e.g. 'ref,due_date'. Read from the "
        "task's criteria.py when omitted.",
    )
    args = parser.parse_args(argv)

    # The job name is "ashgrove-<task>-<tag>" and both halves carry hyphens,
    # so it cannot be split -- match the longest real task directory instead.
    task = args.task or _task_from_job(args.job.name)
    key = tuple(args.key.split(",")) if args.key else _key_from_criteria(task)
    return classify(args.job, task, key)


def _task_from_job(job_name: str) -> str:
    stem = job_name.removeprefix("ashgrove-")
    names = sorted(
        (p.name for p in TASKS.iterdir() if p.is_dir()), key=len, reverse=True
    )
    for name in names:
        if stem.startswith(name):
            return name
    raise SystemExit(f"cannot tell which task {job_name!r} is; pass --task")


def _key_from_criteria(task: str) -> tuple[str, ...] | None:
    """The grader's own row key, so the diff groups rows the way it does."""

    path = TASKS / task / "tests" / "criteria.py"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        if line.startswith("KEY ="):
            value = line.split("=", 1)[1].strip()
            if value.startswith("("):
                return tuple(
                    part.strip().strip("\"'")
                    for part in value.strip("()").split(",")
                    if part.strip()
                )
            return (value.strip("\"'"),)
    return None


if __name__ == "__main__":
    sys.exit(main())

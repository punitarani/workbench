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
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"


def _trials(job: Path) -> list[Path]:
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _deliverable(task: str) -> str | None:
    """The file the grader actually reads, named in the task's own criteria."""

    grade = TASKS / task / "tests" / "answer" / "grade.py"
    if not grade.is_file():
        return None
    match = re.search(r'^D\s*=\s*["\']([^"\']+)["\']', grade.read_text(), re.M)
    return match.group(1) if match else None


def _submitted(trial: Path, task: str | None = None) -> dict | None:
    """What the agent wrote, if the verifier kept it.

    The *deliverable*, not merely the first JSON file lying around. Agents
    leave their working out: one glm-5.2 trial here shipped
    `follow_through.json` beside `all_thread_ids.json` and six
    `messages_part*.json` scratch files, and taking the alphabetically
    first would have diffed the scratch pad against the oracle and called
    the result a model failure.

    Falling back to any dict-shaped file is still right when a task has no
    `D =` line to read, but the named one always wins.
    """

    root = trial / "verifier"
    if not root.is_dir():
        return None
    wanted = _deliverable(task) if task else None
    candidates = sorted(root.glob("submitted-*.json"))
    if wanted:
        # `submitted-<name>` is how test.sh preserves it.
        candidates.sort(key=lambda p: p.name != f"submitted-{wanted}")
    for path in candidates:
        try:
            loaded = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(loaded, dict):
            if wanted and path.name != f"submitted-{wanted}":
                print(
                    f"    (note: {wanted} is absent; reading {path.name}, which "
                    "is the agent's working file and not its answer)"
                )
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
    print(
        f"    rows: oracle {len(want)}, agent {len(got)}, "
        f"missing {len(missing)}, invented {len(invented)}"
    )
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

    # The list the grader keys on, not merely the first one in the file.
    # tracker-reconciliation answers with two: ten engagements and a hundred
    # and thirty-nine effort lines, and taking the first diffed the narrow
    # half while the wide half was where every miss lived.
    def _keyed(value) -> bool:
        return (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
            and bool(key)
            and all(field in value[0] for field in key)
        )

    rows_field = next(
        (k for k, v in oracle.items() if _keyed(v)),
        next((k for k, v in oracle.items() if isinstance(v, list) and v), None),
    )

    print(f"=== {job.name}: {len(trials)} trial(s), task {task}\n")

    # Whole-task evidence first: it is the same for every criterion, and it
    # is what decides E and T before any individual row is looked at.
    print("--- is the oracle independently confirmed? (T)")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "verify_oracle.py"),
            "--task",
            task,
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
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
        answer = _submitted(trial, task)
        if answer is None:
            print(
                "    (the agent's answer was not preserved -- rerun with the "
                "current test.sh, which copies it into /logs/artifacts)"
            )
            continue
        for field, expected in oracle.items():
            if isinstance(expected, list):
                continue
            actual = answer.get(field)
            if str(actual).strip().casefold() != str(expected).strip().casefold():
                print(f"    {field}: agent {actual!r}, oracle {expected!r}")
        if rows_field and key:
            _diff_rows(answer.get(rows_field) or [], oracle[rows_field], key)

    if rows_field and key:
        _stochastic(trials, oracle[rows_field], rows_field, key, task)

    print(
        "\nVerdict is yours. E if the evidence above shows the fact is not "
        "served or the record contradicts itself; T if the oracle failed its "
        "independent derivation or the instruction does not decide the case; "
        "M only when neither of those holds."
    )
    return 0


def _stochastic(
    trials: list[Path],
    expected: list,
    rows_field: str,
    key: tuple[str, ...],
    task: str,
) -> None:
    """Do independent trials miss the same rows? Then it is not the model.

    This is the one mechanical test for T that does not go through the
    rule, and it is the check whose absence cost this project two wrong
    verdicts in one day. A model reading fifteen hundred message bodies
    makes *stochastic* errors: two runs of it drop overlapping but
    different rows. When two runs drop the byte-identical set, they are
    not both guessing — they are both reading the corpus correctly and
    disagreeing with the oracle, and the oracle is what they have in
    common.

    Both defects found today announce themselves here. Thirteen rows on
    the approval register, twice, identically: the rule admitted
    `sign-off` and the pattern dropped `sign-offs`. Thirty on the
    commitment register, twice, identically: the rule said `by the end of
    the week` and the firm writes `by end of week`. In each case the
    agreement between trials was visible before any message was read, and
    in each case it was not looked at.
    """

    want = {tuple(str(r[k]).strip().casefold() for k in key) for r in expected}
    deliverable = _deliverable(task)
    per_trial: list[tuple[str, frozenset, frozenset]] = []
    for trial in trials:
        # The real deliverable only. `_submitted` falls back to any
        # dict-shaped file so a reader can still see what a failed trial
        # was doing, and that is right for the per-trial dump -- but here
        # it meant a k=9 run with five abandonments fed five scratch pads
        # into the comparison and reported a row "invented by every
        # trial" that no trial had invented.
        if deliverable:
            kept = trial / "verifier" / f"submitted-{deliverable}"
            if not kept.is_file():
                continue
        answer = _submitted(trial, task)
        if answer is None:
            continue
        got = set(_rows_of(answer, rows_field, key))
        per_trial.append((trial.name, frozenset(want - got), frozenset(got - want)))
    if len(per_trial) < 2:
        return

    print("\n--- do the trials fail the same way? (T)")
    for label, index in (("missing", 1), ("invented", 2)):
        groups: dict[frozenset, list[str]] = defaultdict(list)
        for row in per_trial:
            if row[index]:
                groups[row[index]].append(row[0])
        for rows, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(names) < 2:
                continue
            print(
                f"    !! {len(names)} independent trials {label} the SAME "
                f"{len(rows)} row(s), byte for byte."
            )
            print(
                "       Genuine model error is stochastic. Identical failures "
                "are the oracle's, until something that does not share the "
                "solver's rule says otherwise."
            )
            for row in sorted(rows)[:6]:
                print(f"       {row}")
            if len(rows) > 6:
                print(f"       ... and {len(rows) - 6} more")
        if not any(len(names) >= 2 for names in groups.values()):
            # Identical sets are the loud case. Near-identical is the
            # quiet one and it is just as diagnostic: gpt-5.6-sol dropped
            # 20 and 16 rows from the same 25 on the bounded completion
            # register, overlapping 80%, and the exact-match test stayed
            # silent while the instruction was the thing at fault.
            # Every trial, including those with none of this failure kind.
            # Filtering the empties made "dropped by every trial" mean
            # "every trial that had any", which inverts the evidence: a
            # trial that invented nothing is the strongest argument that
            # the inventions are not the instruction's fault, and it was
            # the one being excluded.
            sets = [row[index] for row in per_trial]
            # What a systematic defect looks like is a row *every* trial
            # drops, not a high-water pairwise overlap. With four trials
            # there are six pairs, and reporting the worst of them flagged
            # commitment-follow-through at 64% when five of the six sat
            # between 4% and 12% and no row was missed by all four.
            # `set.intersection(*sets)` is an unbound method and rejects the
            # frozensets these are; take it from the first element instead.
            everywhere = len(sets[0].intersection(*sets[1:])) if len(sets) > 1 else 0
            pairs = [
                len(a & b) / len(a | b)
                for i, a in enumerate(sets)
                for b in sets[i + 1 :]
                if a | b
            ]
            typical = sorted(pairs)[len(pairs) // 2] if pairs else 0.0
            if everywhere:
                print(
                    f"    !! {label}: {everywhere} row(s) dropped by EVERY "
                    "trial. That is what a rule the instruction does not "
                    "settle looks like. Read them before calling it M."
                )
            elif typical >= 0.5:
                print(
                    f"    !! {label}: no row is dropped by every trial, but "
                    f"the typical pair overlaps {typical:.0%}. Concentrated "
                    "enough to look at before calling it M."
                )
            else:
                extra = f", typical pair overlaps {typical:.0%}" if pairs else ""
                print(
                    f"    {label}: no row dropped by every trial{extra} — "
                    "scattered, consistent with M."
                )


def _rows_of(answer: dict, rows_field: str, key: tuple[str, ...]) -> list[tuple]:
    rows = answer.get(rows_field)
    if not isinstance(rows, list):
        return []
    return [
        tuple(str(r.get(k)).strip().casefold() for k in key)
        for r in rows
        if isinstance(r, dict)
    ]


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

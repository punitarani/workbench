"""Turn a sweep into an adjudication pack: what the models refused, and why.

    uv run python scripts/diagnose.py --dataset merrick \
        --task live-commitment-register --tag opus-v10-k3 --tag glm-v10-k3

**The stage this replaces cost a day by hand.** A register shipped with
eleven of its twenty rows wrong. Three model families declined all eleven,
the transcripts agreed with the models, and the oracle was the thing they
had in common. Finding that is mechanical; only the last step is judgement.

So this does the mechanical part and stops:

1. **Loss per criterion.** Which of `row_f1`, `row_facts` and the scalars
   the score actually went on. A scalar reading 0.0 for every trial of every
   model, while the counts-of-what-was-read read 1.0, means the models
   opened the whole corpus and disagree with the key -- not with each other.

2. **Rows every trial declined.** Genuine model error is stochastic; two
   runs drop overlapping but different rows. A row that EVERY trial declines
   is a claim about the answer key. Trials with no misses are included on
   purpose: filtering them turns "declined by every trial" into "declined by
   every trial that declined something", which excludes the strongest
   evidence *against* a defect.

3. **Rows the models produced that the key has no row for**, and whether
   the key holds the same pair under a different value -- a wrong date reads
   as one miss and one invention, and the pair is the tell.

4. **The evidence, with no pattern applied.** For every disputed row it
   prints what the key cites and, where the task's solver exposes a reader,
   the speaker's whole contribution. Read against the source, never against
   the rule that produced the row: re-running the pattern that made a row
   cannot disagree with it.

What it does NOT do is decide. It prints; a reader adjudicates. Every
attempt to automate that step so far has just been the answer key wearing a
different hat.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _trials(job: Path, task: str | None = None) -> list[Path]:
    """Trials in a job, optionally only one task's.

    A screen job holds several tasks at once and names each trial
    `<task>__<suffix>`. Reading them all would compare one task's
    submissions against another's key -- which produces a page of confident
    nonsense rather than an error.
    """

    if not job.is_dir():
        return []
    found = sorted(p for p in job.iterdir() if (p / "verifier").is_dir())
    if task is None:
        return found
    return [p for p in found if p.name.rsplit("__", 1)[0] == task]


def _submitted(trial: Path, deliverable: str) -> dict | None:
    path = trial / "verifier" / f"submitted-{deliverable}"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def _deliverable_of(criteria: Path) -> str | None:
    import ast

    tree = ast.parse(criteria.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DELIVERABLE":
                    return ast.literal_eval(node.value)
    return None


def _literal(criteria: Path, name: str):
    import ast

    tree = ast.parse(criteria.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError:
                        return None
    return None


def criteria_table(task_dir: Path, jobs: list[Path], task: str) -> None:
    """Per-criterion values, every trial, so the loss is attributable."""

    print("── where the score went ──\n")
    rows: list[tuple[str, str, dict]] = []
    names: list[str] = []
    for job in jobs:
        for trial in _trials(job, task):
            details = trial / "verifier" / "reward-details.json"
            if not details.is_file():
                continue
            data = json.loads(details.read_text())
            values = {
                item["name"]: item["value"]
                for half in ("answer", "process")
                for item in data.get(half, {}).get("criteria", [])
            }
            for key in values:
                if key not in names:
                    names.append(key)
            rows.append((job.name.split("-")[-2], trial.name[-8:], values))
    if not rows:
        print("  no graded trials found\n")
        return
    head = "".join(f"{name[:11]:>13s}" for name in names)
    print(f"  {'tag':10s} {'trial':9s}{head}")
    print("  " + "-" * (20 + 13 * len(names)))
    for tag, trial, values in rows:
        cells = "".join(f"{values.get(name, float('nan')):13.3f}" for name in names)
        print(f"  {tag:10s} {trial:9s}{cells}")
    print()
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    deliverable = _deliverable_of(task_dir / "tests" / "criteria.py")
    for name in names:
        seen = [v.get(name) for _, _, v in rows if name in v]
        if not seen or not all(value == 0.0 for value in seen):
            continue
        # Nobody earned it. That is two different findings, and reporting
        # them as one nearly deleted a criterion that was doing the whole
        # job of discriminating between tiers.
        #
        # If the answers STRADDLE the key, the key is right and the readers
        # are imprecise: a hard criterion, graded exact-match, on a quantity
        # too large to hit. If they all sit on ONE side, the readers agree
        # with each other and disagree with the key, which is the signature
        # of a convention mismatch and a claim about the key.
        truth = oracle.get(name)
        answers = []
        if deliverable is not None and isinstance(truth, (int, float)):
            for job in jobs:
                for trial in _trials(job, task):
                    got = _submitted(trial, deliverable)
                    if isinstance(got, dict) and isinstance(
                        got.get(name), (int, float)
                    ):
                        answers.append(got[name])
        if len(answers) >= 3 and any(a < truth for a in answers) and any(
            a > truth for a in answers
        ):
            spread = f"{min(answers)}..{max(answers)}"
            print(
                f"  ?? `{name}` is 0.000 in all {len(seen)} trials, but the answers "
                f"STRADDLE\n     the key ({spread} against {truth}). The key is "
                "right and the readers are\n     imprecise -- a hard criterion "
                "graded exact-match, not a defect. Consider\n     whether an "
                "exact grade on a quantity this size can express a near miss."
            )
        else:
            near = f" (answers {min(answers)}..{max(answers)} vs {truth})" if answers else ""
            print(
                f"  !! `{name}` is 0.000 in all {len(seen)} trials{near}. A criterion "
                "no trial of any\n     tier ever earns, with no answer on the other "
                "side of the key, is a claim\n     about the key, not about the tier."
            )
    print()


def row_verdicts(task_dir: Path, jobs: list[Path], task: str) -> list[tuple]:
    """Rows every trial declined, and rows no key row matches."""

    criteria = task_dir / "tests" / "criteria.py"
    deliverable = _deliverable_of(criteria)
    rows_key = _literal(criteria, "ROWS")
    key = tuple(_literal(criteria, "KEY") or ())
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    truth = {tuple(str(r[k]).strip() for k in key): r for r in oracle[rows_key]}

    submissions: dict[str, set] = {}
    for job in jobs:
        for trial in _trials(job, task):
            answer = _submitted(trial, deliverable)
            if answer is None:
                continue
            got = {
                tuple(str(r.get(k, "")).strip() for k in key)
                for r in answer.get(rows_key, [])
                if isinstance(r, dict)
            }
            submissions[f"{job.name.split('-')[-2]}/{trial.name[-6:]}"] = got

    total = len(submissions)
    if not total:
        print("── no submissions to compare ──\n")
        return []
    missed: Counter = Counter()
    invented: Counter = Counter()
    for got in submissions.values():
        for row in truth:
            if row not in got:
                missed[row] += 1
        for row in got - set(truth):
            invented[row] += 1

    print(f"── rows against {total} trial(s) ──\n")
    disputed = []
    for row, count in sorted(missed.items(), key=lambda kv: (-kv[1], kv[0])):
        mark = "  <== EVERY trial" if count == total else ""
        print(f"  declined {count}/{total}  {' | '.join(row)}{mark}")
        if count == total:
            disputed.append(row)
    if not missed:
        print("  every key row was produced by every trial")
    print(f"\n  produced by every trial: {len(truth) - len(missed)} of {len(truth)}\n")

    if invented:
        print("── rows the models produced that the key has no row for ──\n")
        pairs = {row[:-1] for row in truth} if len(key) > 1 else set()
        for row, count in sorted(invented.items(), key=lambda kv: (-kv[1], kv[0])):
            note = ""
            if len(key) > 1 and row[:-1] in pairs:
                held = [r[-1] for r in truth if r[:-1] == row[:-1]]
                note = f"   (the key holds this pair at {held[0]!r})"
            print(f"  invented {count}/{total}  {' | '.join(row)}{note}")
        print()

    # A row every trial declined AND answered at a different value is not a
    # row they missed. It is a row they disagreed with, and the distinction
    # decides how it has to be adjudicated.
    #
    # This exists because the obvious adjudication is unsound and looked
    # sound. Asked whether the passage the key cites carries the commitment
    # the key holds, three judges said yes, unanimously, quoting the words
    # -- and they were right. The row was still wrong: a LATER turn by the
    # same person superseded it, and the rule had not admitted that turn.
    # Nothing about the cited passage could have revealed that, because
    # what made the row wrong was a sentence the judges were never shown.
    #
    # So the evidence set has to cover what decides the row, not what
    # produced it. When the trials name a different value, their value is
    # the other half of the evidence.
    if len(key) > 1:
        contested = []
        for row, count in missed.items():
            if count != total:
                continue
            rival = [
                (other, n)
                for other, n in invented.items()
                if other[:-1] == row[:-1] and other[-1] != row[-1]
            ]
            if rival:
                contested.append((row, sorted(rival, key=lambda kv: -kv[1])))
        if contested:
            print("── rows the trials ANSWERED DIFFERENTLY, not rows they missed ──\n")
            for row, rival in contested:
                print(f"  {' | '.join(row[:-1])}")
                print(f"      key     {row[-1]!r}  declined by {total} of {total}")
                for other, n in rival:
                    print(f"      trials  {other[-1]!r}  produced by {n} of {total}")
                print("  <== CONTESTED. Adjudicate the key's passage AND the passage")
                print("      behind the trials' value TOGETHER. A judge shown only the")
                print(
                    "      key's own evidence can confirm that passage and still leave"
                )
                print(
                    "      the row wrong, because what makes it wrong is elsewhere.\n"
                )
    return disputed


def evidence(task_dir: Path, disputed: list[tuple]) -> None:
    """What the key cites for each disputed row, with no pattern applied."""

    if not disputed:
        return
    criteria = task_dir / "tests" / "criteria.py"
    key = tuple(_literal(criteria, "KEY") or ())
    rows_key = _literal(criteria, "ROWS")
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    print("── what the key cites for each disputed row ──")
    print("   Read these against the source. Re-running the pattern that")
    print("   produced a row cannot disagree with it.\n")
    for row in disputed:
        found = next(
            (
                r
                for r in oracle[rows_key]
                if tuple(str(r[k]).strip() for k in key) == row
            ),
            None,
        )
        if found is None:
            continue
        print(f"  {' | '.join(row)}")
        for field, value in found.items():
            if field not in key:
                print(f"      {field}: {value}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="one per sweep; pass every tier's, so a row declined by all of "
        "them is visible as such",
    )
    parser.add_argument(
        "--job",
        action="append",
        default=[],
        help="a job directory by name, for jobs a tag cannot address -- "
        "`screen.py` runs many tasks under one job, so its name carries no "
        "task and `--tag` cannot reach it",
    )
    args = parser.parse_args(argv)

    if not (args.tag or args.job):
        parser.error("pass at least one --tag or --job")

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    if not (task_dir / "tests" / "oracle.json").is_file():
        raise SystemExit(f"{args.task}: not built — no tests/oracle.json")
    jobs = [REPO / "jobs" / f"{args.dataset}-{args.task}-{tag}" for tag in args.tag]
    jobs += [REPO / "jobs" / name for name in args.job]
    absent = [job.name for job in jobs if not job.is_dir()]
    if absent:
        raise SystemExit(f"no such job(s): {absent}")

    print(f"\n=== {args.task} — {len(jobs)} sweep(s) ===\n")
    criteria_table(task_dir, jobs, args.task)
    disputed = row_verdicts(task_dir, jobs, args.task)
    evidence(task_dir, disputed)
    if disputed:
        print(
            f"  {len(disputed)} row(s) declined by every trial. Genuine model "
            "error is stochastic;\n  agreement this complete is a claim about "
            "the key. Adjudicate each against the\n  raw source before "
            "recording any of them as a model failure.\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

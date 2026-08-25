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


def _trials(job: Path) -> list[Path]:
    if not job.is_dir():
        return []
    return sorted(p for p in job.iterdir() if (p / "verifier").is_dir())


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


def criteria_table(jobs: list[Path]) -> None:
    """Per-criterion values, every trial, so the loss is attributable."""

    print("── where the score went ──\n")
    rows: list[tuple[str, str, dict]] = []
    names: list[str] = []
    for job in jobs:
        for trial in _trials(job):
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
    for name in names:
        seen = [v.get(name) for _, _, v in rows if name in v]
        if seen and all(value == 0.0 for value in seen):
            print(
                f"  !! `{name}` is 0.000 in all {len(seen)} trials. A criterion no "
                "trial of any\n     tier ever earns is a claim about the key, not "
                "about the tier."
            )
    print()


def row_verdicts(task_dir: Path, jobs: list[Path]) -> list[tuple]:
    """Rows every trial declined, and rows no key row matches."""

    criteria = task_dir / "tests" / "criteria.py"
    deliverable = _deliverable_of(criteria)
    rows_key = _literal(criteria, "ROWS")
    key = tuple(_literal(criteria, "KEY") or ())
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    truth = {tuple(str(r[k]).strip() for k in key): r for r in oracle[rows_key]}

    submissions: dict[str, set] = {}
    for job in jobs:
        for trial in _trials(job):
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
        required=True,
        help="one per sweep; pass every tier's, so a row declined by all of "
        "them is visible as such",
    )
    args = parser.parse_args(argv)

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    if not (task_dir / "tests" / "oracle.json").is_file():
        raise SystemExit(f"{args.task}: not built — no tests/oracle.json")
    jobs = [REPO / "jobs" / f"{args.dataset}-{args.task}-{tag}" for tag in args.tag]
    absent = [job.name for job in jobs if not job.is_dir()]
    if absent:
        raise SystemExit(f"no such job(s): {absent}")

    print(f"\n=== {args.task} — {len(jobs)} sweep(s) ===\n")
    criteria_table(jobs)
    disputed = row_verdicts(task_dir, jobs)
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

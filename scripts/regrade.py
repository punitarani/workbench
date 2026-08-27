"""Re-score saved deliverables against the current answer key.

    uv run python scripts/regrade.py --dataset merrick \
        --task commitment-revision-register --tag opus-rev-k3

**Why this exists.** Correcting an oracle used to cost a full sweep per
tier. It should not: the agent's work is already on disk, the instruction
it read has not moved, and a corrected key is a better grader of the same
work. Re-running would measure a fresh sample of the model instead --
which is a different, noisier question, and one that hides whether the
correction moved the score or the dice did.

**When this is valid, and when it is not.** Valid when only the KEY
changed: a rule implementation corrected, an oracle refreshed, a criterion
reweighted. Not valid when the BRIEF changed, because then the agent was
answering a different question and its old deliverable is an answer to
that one.

Checked rather than assumed, and the check is narrow on purpose. Trials do
not keep a copy of `instruction.md`, but the brief is embedded in the
agent's own trajectory, so this asks the only question that matters here:
does every field the current key GRADES appear in the brief that trial was
actually given? A trial never asked for `first_due` cannot be scored on
it. Hashing the instruction would be stricter and useless -- the brief is
reformatted into a larger prompt, so a digest would refuse every trial
ever run.

This paragraph originally described a comparison this file did not
perform: it printed a digest and compared nothing. A documented check that
does not exist is worse than no check, because the reader stops looking.

The score is recomputed from the task's own `criteria.py` and
`criteria_base`, never from a copy of the weights kept here -- a
hand-copied weight table is the thing that silently disagrees with the
grader it is imitating.
"""

import argparse
import importlib.util
import json
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _answered_this_brief(trial: Path, graded: set[str], anchor: str) -> set[str]:
    """Fields the current key grades that the trial's own brief never named.

    Empty means the trial answered today's question and its saved
    deliverable can be re-scored. Anything else means it did not.

    **A witness has to be testifying before its silence means anything.**
    Trajectories are compacted, truncated, and sometimes never record the
    prompt at all, so a field missing from one is not evidence the brief
    lacked it. The first version of this check ignored that and reported
    that a trial had "never been asked for owner" -- a trial whose every
    row was keyed on owner. It refused six real measurements that way, in
    the direction that looks like diligence.

    So `anchor` -- the name of the file the brief tells the agent to write
    -- has to appear first. Absent, this trajectory says nothing about any
    brief and the trial is treated as comparable. Present, a missing graded
    field is real evidence the brief was an older one.
    """

    trajectory = trial / "agent" / "trajectory.json"
    if not trajectory.is_file():
        return set()
    seen = trajectory.read_text(encoding="utf-8", errors="replace")
    if anchor not in seen:
        return set()
    return {field for field in graded if f'"{field}"' not in seen and field not in seen}


def _score(task_dir: Path, workspace: Path) -> dict[str, float] | None:
    """One trial's answer-dimension criteria, at the grader's own weights."""

    tests = task_dir / "tests"
    # rewardkit lives in the Harbor verifier image, not this venv. The repo
    # already carries one stub for every caller that needs it -- writing a
    # second here is the drift that stub's own docstring warns about.
    if "rewardkit" not in sys.modules:
        stub = _load(REPO / "tests" / "rewardkit_stub.py", "rewardkit_stub")
        sys.modules["rewardkit"] = stub.calling()
    sys.path.insert(0, str(tests))
    base = _load(tests / "criteria_base.py", "criteria_base")
    criteria = _load(tests / "criteria.py", "criteria")
    oracle = json.loads((tests / "oracle.json").read_text())

    # Harbor keeps the trial's answer as `submitted-<name>`, and the grader
    # reads `<name>` from a workspace. Stage a copy under the name the
    # grader expects rather than teaching the grader a second filename --
    # the grader here has to be the one the verifier runs, unmodified.
    saved = workspace / f"submitted-{criteria.DELIVERABLE}"
    if not saved.is_file():
        return None
    staged = Path(tempfile.mkdtemp(prefix="regrade-"))
    shutil.copy(saved, staged / criteria.DELIVERABLE)
    workspace = staged

    if base.submitted(workspace, criteria.DELIVERABLE) is None:
        return None

    restated = frozenset(getattr(criteria, "RESTATED_FROM_BRIEF", ()))
    derived = frozenset(getattr(criteria, "DERIVED_FROM_ROWS", ()))
    rows, key = criteria.ROWS, list(criteria.KEY)

    parts: list[tuple[str, float, float]] = []
    for name in sorted(k for k, v in oracle.items() if not isinstance(v, list)):
        if name in restated or name in derived:
            continue
        got = base.scalar(workspace, criteria.DELIVERABLE, name, oracle[name], 0)
        parts.append((name, float(got), 1.0))
    parts.append((
        f"{rows}.f1",
        base.row_f1(workspace, criteria.DELIVERABLE, rows, key, oracle[rows]),
        5.0,
    ))
    parts.append((
        "row_facts",
        base.row_fields(
            workspace, criteria.DELIVERABLE, rows, key, oracle[rows], dict(criteria.FIELDS)
        ),
        3.0,
    ))
    total = sum(weight for _, _, weight in parts)
    scored = {name: value for name, value, _ in parts}
    scored["__score__"] = sum(value * weight for _, value, weight in parts) / total
    return scored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--tag", action="append", required=True)
    args = parser.parse_args()

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    sys.path.insert(0, str(task_dir / "tests"))
    if "rewardkit" not in sys.modules:
        stub = _load(REPO / "tests" / "rewardkit_stub.py", "rewardkit_stub")
        sys.modules["rewardkit"] = stub.calling()
    criteria = _load(task_dir / "tests" / "criteria.py", "criteria")
    graded = tuple(criteria.KEY) + tuple(criteria.FIELDS)
    print(f"=== regrading {args.task} against the current key ===")
    print(f"  graded fields: {', '.join(graded)}\n")

    for tag in args.tag:
        job = REPO / "jobs" / f"{args.dataset}-{args.task}-{tag}"
        if not job.is_dir():
            print(f"  {tag}: no such job\n")
            continue
        scores, was = [], []
        for trial in sorted(p for p in job.iterdir() if p.is_dir()):
            verifier = trial / "verifier"
            missing = _answered_this_brief(trial, set(graded), criteria.DELIVERABLE)
            if missing:
                print(
                    f"  {tag} {trial.name[-8:]}: answered a different brief — it was "
                    f"never asked for {', '.join(sorted(missing))}. Not comparable; "
                    "re-run it."
                )
                continue
            got = _score(task_dir, verifier)
            old = verifier / "reward.json"
            if old.is_file():
                was.append(json.loads(old.read_text())["reward"])
            if got is None:
                print(f"  {tag} {trial.name[-8:]}: no deliverable — not a score")
                continue
            scores.append(got["__score__"])
            print(
                f"  {tag} {trial.name[-8:]}  {got['__score__']:.3f}   "
                + "  ".join(
                    f"{k}={v:.3f}" for k, v in got.items() if k != "__score__"
                )
            )
        if scores:
            now, before = statistics.mean(scores), statistics.mean(was) if was else None
            band = "IN BAND" if 0.2 <= now <= 0.8 else ("ABOVE" if now > 0.8 else "below")
            moved = f"  (was {before:.3f})" if before is not None else ""
            print(f"  {tag}: mean {now:.3f}{moved}  {band}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""How often a tier produced the deliverable, per sweep.

    uv run python scripts/completion.py --dataset delegation --task mail-promise-register

How well a model answers and how often it manages to answer are different
facts, and only one of them is about the model. This reports the second,
which nothing else does: `band.py` excludes a trial that wrote nothing and
says so in passing, and a score table cannot show it at all.

**It counts TRIALS against the task's declared deliverable, not files.**
Counting `submitted-*.json` reports 15 answers from 3 trials, because
agents leave working files beside the real one -- `submitted-meetings_meta.json`
next to `submitted-slippage_register.json`. The same confusion once made a
scratch pad look like a deliverable scoring 0.414 on the row set.
"""

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _deliverable(dataset: str, task: str) -> str:
    criteria = REPO / "datasets" / dataset / "tasks" / task / "tests" / "criteria.py"
    found = re.search(r'^DELIVERABLE\s*=\s*"([^"]+)"', criteria.read_text(), re.M)
    if found is None:
        raise SystemExit(f"{dataset}/{task}: criteria.py names no DELIVERABLE")
    return found.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args(argv)

    wanted = _deliverable(args.dataset, args.task)
    prefix = f"{args.dataset}-{args.task}-"
    total = answered = 0
    for job in sorted((REPO / "jobs").glob(f"{prefix}*")):
        if not job.is_dir():
            continue
        trials = [t for t in job.iterdir() if t.is_dir()]
        if not trials:
            continue
        got = [t for t in trials if (t / "verifier" / f"submitted-{wanted}").is_file()]
        graded = [t for t in trials if (t / "verifier" / "reward.json").is_file()]
        # A reward file exists even for a trial that wrote nothing, holding
        # 0.0 -- so completion has to be counted on the DELIVERABLE, which
        # is what the score aggregator keys on. Counting reward files
        # reported 92% where the answer was 65%.
        total += len(trials)
        answered += len(got)
        print(
            f"  {job.name.removeprefix(prefix):16} "
            f"{len(got)}/{len(trials)} answered, {len(graded)} scored"
        )
    if total:
        print(f"  ---- {answered}/{total} = {answered / total:.0%} across every sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

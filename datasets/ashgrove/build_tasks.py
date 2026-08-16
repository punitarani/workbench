"""Build Ashgrove task environments from its world log.

    uv run python datasets/ashgrove/build_tasks.py [--task NAME ...]

Materializes one seatless bundle from the epoch log and stages it for
every task under ``tasks/`` — seatless because these are firm-wide audits
that read across seats, the same choice the Hartwell tasks make. Each
task's reference solver runs against the fresh bundle and its output must
match the committed oracle byte for byte; ``--refresh-truth`` is the only
way to move that line, and it is a deliberate act.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from workbench.analysis.reachability import unreachable
from workbench.environment.materialize import materialize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hartwell"))

from harbor_stage import stage  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
DEFAULT_LOG = REPO / "out" / "ashgrove" / "epoch" / "world.jsonl"
SHARED_BUNDLE = REPO / "out" / "ashgrove" / "bundle"


def degenerate(answer: dict) -> list[str]:
    """Row fields that carry the same value in every row.

    A constant column is a criterion that grades nothing: an agent that
    never looks it up and writes the majority value scores full marks on
    it. Both new tasks this dataset gained were degenerate on their first
    real world — 88 of 90 documents undelivered, and not one workpaper
    with a second author — and both looked healthy right up until the
    distributions were counted.

    Reported rather than fatal. Sparseness can be the finding (few
    documents ever reach a client, and that is the point), so this is a
    number for a person to weigh, not a gate to trip.
    """

    reports = []
    for key, rows in answer.items():
        if not isinstance(rows, list) or not rows:
            continue
        if not isinstance(rows[0], dict):
            continue
        # A handful of rows cannot produce a partial score. Six of seven
        # tasks here answered with four to ten rows and every rollout came
        # back 1.000 or near zero: with so little to get partly right, the
        # grade is a verdict on the rule and not a measure of the work.
        if len(rows) < 12:
            reports.append(
                f"{key} has only {len(rows)} rows — too thin for partial credit"
            )
        if len(rows) < 5:
            continue
        for field in rows[0]:
            values = {json.dumps(row.get(field), sort_keys=True) for row in rows}
            if len(values) == 1:
                reports.append(
                    f"{key}.{field} is {values.pop()} in all {len(rows)} rows"
                )
    return reports


def build(world_log: Path, names: list[str], refresh: bool) -> int:
    env = materialize(world_log, SHARED_BUNDLE, seat=None)
    print(f"materialized {env.event_count} events -> {SHARED_BUNDLE}")
    if env.skipped_renders:
        for skip in env.skipped_renders:
            print(f"  render skipped: {skip}")

    selected = names or sorted(p.name for p in TASKS.iterdir() if p.is_dir())
    for name in selected:
        task = TASKS / name
        solver = task / "solution" / "solve.py"
        if not solver.exists():
            print(f"{name}: no reference solver; skipping")
            continue
        produced = SHARED_BUNDLE / "workspace" / f"{name}-answer.json"
        subprocess.run(
            [sys.executable, str(solver), str(produced)],
            check=True,
            env={
                "WORKBENCH_STATE": str(SHARED_BUNDLE / "state"),
                "PATH": "/usr/bin:/bin",
            },
        )
        answer = json.loads(produced.read_text())
        produced.unlink()
        oracle_path = task / "tests" / "oracle.json"
        if refresh or not oracle_path.exists():
            oracle_path.parent.mkdir(parents=True, exist_ok=True)
            oracle_path.write_text(json.dumps(answer, indent=1) + "\n")
            print(f"{name}: oracle written")
        elif json.loads(oracle_path.read_text()) != answer:
            raise SystemExit(
                f"{name}: the reference solver no longer reproduces its oracle. "
                "Rebuild the world or pass --refresh-truth deliberately."
            )
        else:
            print(f"{name}: oracle verified")

        # An oracle the tools cannot spell is not an answer key, it is a
        # coin flip on which internal vocabulary the agent guesses. This
        # blocks the task rather than letting it produce a plausible score.
        missing = unreachable(answer, SHARED_BUNDLE / "state")
        if missing:
            raise SystemExit(
                f"{name}: the oracle names {len(missing)} value(s) no tool "
                f"ever serves: {missing[:8]}. Express the rule in something "
                "the surfaces expose, or the score measures the guess."
            )
        print(f"{name}: oracle reachable through the tools")

        for report in degenerate(answer):
            print(f"{name}: DEGENERATE {report}")

        bundle = task / "bundle"
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.copytree(SHARED_BUNDLE, bundle)
        staged = stage(bundle, task / "environment", repo_root=REPO)
        print(f"{name}: staged -> {staged}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--refresh-truth", action="store_true")
    args = parser.parse_args(argv)
    return build(args.log, args.task, args.refresh_truth)


if __name__ == "__main__":
    raise SystemExit(main())

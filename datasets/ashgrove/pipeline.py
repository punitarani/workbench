"""The whole Ashgrove pipeline, in the order it has to happen.

    uv run --env-file .env python datasets/ashgrove/pipeline.py \
        --log out/ashgrove/epoch-r12/world.jsonl --refresh-truth
    uv run --env-file .env python datasets/ashgrove/pipeline.py --rollouts -k 3

Five stages, each of which can refuse:

1. **audit** the recorded world against the realism gates.
2. **build** — coherence check, materialize, run every reference solver,
   compare or refresh each oracle, prove its identifiers are served, and
   report any degenerate column.
3. **verify** — re-derive every oracle a second way, from the log rather
   than from the database the solvers read.
4. **rollouts** — every task, every model, k trials, per-criterion means.
5. **classify** — for each criterion below 1.0, the evidence for calling it
   a model failure rather than a defect.

The order is not arbitrary and the refusals are the point. A world that
contradicts itself must not reach a solver; an oracle that fails its
independent derivation must not reach a rollout; and a rollout that scores
below 1.0 must not be called a model failure until stage 5 has been read.
Every one of those three has been violated in this project, and each cost
more than the check would have.
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TASKS = HERE / "tasks"
DEFAULT_LOG = REPO / "out" / "ashgrove" / "epoch" / "world.jsonl"


def run(label: str, command: list[str], *, fatal: bool = True) -> int:
    print(f"\n{'=' * 72}\n== {label}\n{'=' * 72}", flush=True)
    code = subprocess.run(command, cwd=REPO).returncode
    if code and fatal:
        print(
            f"\n{label}: FAILED ({code}). Stopping here on purpose — every "
            "later stage would be measuring something this one just said "
            "cannot be trusted.",
            file=sys.stderr,
        )
        raise SystemExit(code)
    return code


def task_names() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if p.is_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--refresh-truth", action="store_true")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument(
        "--rollouts",
        action="store_true",
        help="also spend money: run every task through every model",
    )
    parser.add_argument("-k", "--trials", type=int, default=3)
    parser.add_argument(
        "--models",
        default="opus-5,glm-5.2",
        help="comma-separated. gpt-5.6-sol is deliberately absent: it fails "
        "tool calling under both codex and opencode and its zeros are "
        "harness artefacts, not capability.",
    )
    args = parser.parse_args(argv)

    python = [sys.executable]
    selected = args.task or task_names()

    run(
        "1. audit the world",
        [*python, str(HERE / "run_epoch.py"), "audit", "--out", str(args.log.parent)],
    )

    build = [*python, str(HERE / "build_tasks.py"), "--log", str(args.log)]
    if args.refresh_truth:
        build.append("--refresh-truth")
    for name in args.task:
        build += ["--task", name]
    run("2. build: coherence, materialize, oracles, reachability, degeneracy", build)

    verify = [*python, str(HERE / "verify_oracle.py"), "--log", str(args.log)]
    for name in args.task:
        verify += ["--task", name]
    run("3. verify: derive every oracle a second way, from the log", verify)

    if not args.rollouts:
        print("\nStages 1-3 green. Add --rollouts to spend money on 4 and 5.")
        return 0

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    jobs = []
    for model in models:
        for name in selected:
            tag = f"{model}-k{args.trials}"
            run(
                f"4. rollout {name} x {model} x {args.trials}",
                [
                    *python,
                    str(HERE / "run_rollouts.py"),
                    "run",
                    name,
                    "--model",
                    model,
                    "-k",
                    str(args.trials),
                    "--tag",
                    tag,
                ],
                fatal=False,
            )
            jobs.append((name, f"ashgrove-{name}-{tag}"))

    for name, job in jobs:
        path = REPO / "jobs" / job
        if path.is_dir():
            run(
                f"5. classify {job}",
                [*python, str(HERE / "classify_misses.py"), str(path), "--task", name],
                fatal=False,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Screen many tasks in one harbor job, to find the ceiling ones cheaply.

    uv run python scripts/screen.py --dataset merrick --model opus-5 --k 1 \
        --task live-commitment-register --task off-sense-register

**Why this exists.** A task whose rule a model can turn into a program
scores 1.000, and no window, corpus or arithmetic changes that. Four of the
first five tasks measured this way were at ceiling, and each cost a full
three-model sweep — nine trials, hours apiece — to learn one bit.

So the loop is: screen at k=1 against the strongest tier first. A 1.000
there is a design verdict and the task goes back to the drawing board; only
a task that survives is worth the three-model sweep. The screen is not a
score and this file never reports it as one -- `band.py` reads sweeps.

**One job, many tasks.** `harbor run` takes a list, and the gateway, the
image pull and the agent install are per-job rather than per-task. Screening
eight tasks in one job costs about what two cost in eight jobs. Tags carry
`screen-` so the aggregator's own tags can never collide with them.
"""

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from rollout import TIERS, _refuse_unbuilt  # noqa: E402

from adapters.harbor_matrix.gateway import (  # noqa: E402
    GatewayConfig,
    ProviderGateway,
)

# Above this a task is not measuring the tier, whatever else is true of it.
# Not 1.000: a task can be at ceiling and still lose a rounding-sized sliver
# on one criterion, and calling that "in band" would be the same mistake in
# the other direction.
CEILING = 0.95


def config(
    dataset: str,
    tasks: list[str],
    model: str,
    tag: str,
    k: int,
    port: int,
    concurrency: int,
    token: str,
) -> dict:
    paths = []
    for task in tasks:
        path = REPO / "datasets" / dataset / "tasks" / task
        if not path.is_dir():
            raise SystemExit(f"no task at {path}")
        _refuse_unbuilt(path, task)
        paths.append({"path": str(path)})
    return {
        "job_name": f"{dataset}-screen-{tag}",
        "jobs_dir": str(REPO / "jobs"),
        "n_attempts": k,
        "agent_timeout_multiplier": 4.0,
        "agent_setup_timeout_multiplier": 6.0,
        "n_concurrent_trials": concurrency,
        "quiet": True,
        "retry": {"max_retries": 2},
        "agents": [
            {
                "name": TIERS[model][0],
                "model_name": TIERS[model][1],
                "n_concurrent": concurrency,
                "extra_allowed_hosts": ["host.docker.internal"],
                "env": {
                    "OPENAI_BASE_URL": f"http://host.docker.internal:{port}/v1",
                    "HARTWELL_GATEWAY_TOKEN": token,
                },
            }
        ],
        "tasks": paths,
    }


def report(job: Path) -> int:
    """Read the screen back. Returns how many tasks are still candidates."""

    if not job.is_dir():
        print(f"  no job at {job}")
        return 0
    scores: dict[str, list[float]] = {}
    for trial in sorted(job.iterdir()):
        reward = trial / "verifier" / "reward.json"
        if not reward.is_file():
            continue
        # Harbor names a trial `<task>__<suffix>`; the task is the stem.
        name = trial.name.rsplit("__", 1)[0]
        try:
            scores.setdefault(name, []).append(
                float(json.loads(reward.read_text())["reward"])
            )
        except ValueError, KeyError, TypeError:
            continue
    if not scores:
        print("  nothing graded yet")
        return 0
    live = 0
    print(f"  {'task':34s} {'trials':>22s} {'mean':>7s}  verdict")
    print("  " + "-" * 74)
    for name, values in sorted(scores.items()):
        mean = sum(values) / len(values)
        if mean >= CEILING:
            verdict = "CEILING — redesign the rule"
        elif mean <= 0.05:
            verdict = "floor — read the log before believing it"
        else:
            verdict = "candidate — worth a three-model sweep"
            live += 1
        shown = str([round(v, 3) for v in sorted(values)])
        print(f"  {name:34s} {shown:>22s} {mean:7.3f}  {verdict}")
    print(f"\n  {live} of {len(scores)} worth sweeping")
    return live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", action="append", default=[], required=True)
    parser.add_argument("--model", default="opus-5", choices=sorted(TIERS))
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--tag", default=None)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="read a finished screen back without running anything",
    )
    args = parser.parse_args(argv)

    tag = args.tag or f"{args.model.split('-')[0]}-k{args.k}"
    job = REPO / "jobs" / f"{args.dataset}-screen-{tag}"
    if args.report_only:
        return 0 if report(job) >= 0 else 1

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; the gateway cannot pin")

    async def run() -> int:
        token = secrets.token_urlsafe(24)
        gateway = ProviderGateway(
            GatewayConfig(
                openrouter_api_key=key,
                gateway_token=token,
                bind_host="0.0.0.0",
                port=0,
            )
        )
        async with gateway:
            cfg = config(
                args.dataset,
                args.task,
                args.model,
                tag,
                args.k,
                gateway.port,
                args.concurrency,
                token,
            )
            out = REPO / "jobs" / f"screen-{args.dataset}-{tag}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(cfg, indent=2))
            print(f"  screening {len(args.task)} task(s) at k={args.k} on {args.model}")
            environment = os.environ.copy()
            roots = [str(REPO / "src")]
            if inherited := environment.get("PYTHONPATH"):
                roots.extend(inherited.split(os.pathsep))
            environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(roots))
            # to_thread, not a blocking call: the gateway is served by this
            # event loop, and blocking it makes every container's first
            # request time out with "stream disconnected" -- a harness
            # failure that reads exactly like a broken task.
            code = await asyncio.to_thread(
                subprocess.call,
                ["harbor", "run", "-c", str(out)],
                env=environment,
            )
            print()
            report(job)
            return code

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())

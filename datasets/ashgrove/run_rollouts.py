"""Run Ashgrove tasks through Harbor and report what each criterion scored.

    uv run --env-file .env python datasets/ashgrove/run_rollouts.py run \
        engagement-time-allocation --model opus-5 -k 3
    uv run python datasets/ashgrove/run_rollouts.py report jobs/ashgrove-...

Two things this exists to fix.

**One trial is not a measurement.** Every Ashgrove score so far was n=1, and
a single rollout of a stochastic agent is a coin flip wearing a decimal point.
``-k`` runs the trials inside one job so they share a gateway and a build, and
the report gives each criterion its mean and its spread across them.

**The harness is not the model.** A sweep of ``gpt-5.6-sol`` returned 0.000 on
three tasks and it looked like a capability result; the trial log showed every
MCP call dying with "tool exec invoked with incompatible payload" and the agent
writing nothing at all. Codex and opencode drive the same gateway -- it routes
``/v1/responses`` and ``/v1/chat/completions`` to the matching OpenRouter
endpoint -- so ``--harness`` swaps the driver without touching the pins, and
``smoke`` proves an agent can reach the tools before a paid sweep assumes it.
"""

import argparse
import asyncio
import json
import os
import secrets
import statistics
import sys
from pathlib import Path

from pydantic import SecretStr

from workbench.adapters.harbor_matrix.gateway import (
    MODEL_ALIASES,
    GatewayConfig,
    ProviderGateway,
)
from workbench.adapters.harbor_matrix.runner import (
    AGENT_TIMEOUT_MULTIPLIER,
    CODEX_COMPACTION_MODE,
    CODEX_VERSION,
    HARTWELL_CODEX_IMPORT_PATH,
    HARTWELL_OPENCODE_IMPORT_PATH,
    OPENCODE_MODEL_PREFIX,
    OPENCODE_VERSION,
    _create_gateway_env_file,
)
from workbench.adapters.harness.openrouter_client import MODEL_PROVIDERS

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
JOBS = REPO / "jobs"


def _api_key() -> str:
    """The OpenRouter credential, read from .env rather than the environment.

    ``uv run --env-file .env`` puts it in os.environ, but the plain
    interpreter does not, and a driver that only works one of those two ways
    is a trap for whoever runs it the other way.
    """

    if key := os.environ.get("OPENROUTER_API_KEY"):
        return key
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENROUTER_API_KEY found in neither environment nor .env")


def _harbor_command(
    task: str,
    *,
    model: str,
    harness: str,
    trials: int,
    concurrency: int,
    gateway_port: int,
    gateway_env_file: Path,
    job_name: str,
) -> tuple[str, ...]:
    """The harbor invocation, in the shape the chosen harness expects.

    Mirrors ``harbor_matrix.runner._task_command`` -- the import path, the
    model spelling, and the agent kwargs all differ by harness, and the
    gateway flags do not.
    """

    if harness == "opencode":
        agent = HARTWELL_OPENCODE_IMPORT_PATH
        # opencode reaches the gateway through its ``openai`` provider, so the
        # alias travels as ``openai/<alias>``; the gateway strips the segment
        # back off and pins the provider chain the same way for either harness.
        model_arg = f"{OPENCODE_MODEL_PREFIX}{model}"
        agent_kwargs: tuple[str, ...] = ("--ak", f"version={OPENCODE_VERSION}")
    else:
        agent = HARTWELL_CODEX_IMPORT_PATH
        model_arg = model
        agent_kwargs = (
            "--ak",
            f"version={CODEX_VERSION}",
            "--ak",
            f"compaction_mode={CODEX_COMPACTION_MODE}",
        )
    return (
        "harbor",
        "run",
        "-p",
        str(TASKS / task),
        "-a",
        agent,
        "-m",
        model_arg,
        "-k",
        str(trials),
        "-n",
        str(concurrency),
        "--n-concurrent-agents",
        str(concurrency),
        "--agent-timeout-multiplier",
        str(AGENT_TIMEOUT_MULTIPLIER),
        *agent_kwargs,
        "--ae",
        f"OPENAI_BASE_URL=http://host.docker.internal:{gateway_port}/v1",
        "--env-file",
        str(gateway_env_file),
        "--allow-agent-host",
        "host.docker.internal",
        "--max-retries",
        "0",
        "-y",
        "-q",
        "-o",
        str(JOBS),
        "--job-name",
        job_name,
    )


async def _run_one(task: str, args: argparse.Namespace, job_name: str) -> int:
    token = secrets.token_urlsafe(32)
    gateway = ProviderGateway(
        GatewayConfig(
            openrouter_api_key=SecretStr(_api_key()),
            gateway_token=SecretStr(token),
            bind_host="0.0.0.0",
            port=0,
        )
    )
    await gateway.start()
    env_file = _create_gateway_env_file(SecretStr(token))
    command = _harbor_command(
        task,
        model=args.model,
        harness=args.harness,
        trials=args.trials,
        concurrency=args.concurrency,
        gateway_port=gateway.port,
        gateway_env_file=env_file,
        job_name=job_name,
    )
    environment = dict(os.environ)
    paths = [str(REPO / "src"), *filter(None, [environment.get("PYTHONPATH")])]
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    try:
        process = await asyncio.create_subprocess_exec(
            *command, cwd=REPO, env=environment
        )
        return await process.wait()
    finally:
        await gateway.stop()
        env_file.unlink(missing_ok=True)


def _trial_dirs(job: Path) -> list[Path]:
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _criteria(trial: Path) -> dict[str, dict[str, float]]:
    """Every criterion of every dimension, keyed ``dimension.name``."""

    details = trial / "verifier" / "reward-details.json"
    if not details.is_file():
        return {}
    try:
        loaded = json.loads(details.read_text())
    except ValueError:
        return {}
    out: dict[str, dict[str, float]] = {}
    for dimension, block in loaded.items():
        if not isinstance(block, dict):
            continue
        for entry in block.get("criteria", []):
            out[f"{dimension}.{entry['name']}"] = {
                "value": float(entry.get("value") or 0.0),
                "weight": float(entry.get("weight") or 0.0),
            }
    return out


def _dimension_scores(trial: Path) -> dict[str, float]:
    reward = trial / "verifier" / "reward.json"
    if not reward.is_file():
        return {}
    try:
        loaded = json.loads(reward.read_text())
    except ValueError:
        return {}
    return {k: float(v) for k, v in loaded.items() if isinstance(v, (int, float))}


def report(job: Path) -> int:
    """Per-criterion mean and spread across a job's trials.

    A criterion that is 1.0 in every trial is not discriminating and a
    criterion that is 0.0 in every trial is either a real miss or a defect;
    the spread column is what tells those apart from a lucky single run.
    """

    trials = _trial_dirs(job)
    if not trials:
        print(f"{job.name}: no trials", file=sys.stderr)
        return 1
    per_trial = [_criteria(t) for t in trials]
    names = sorted({name for trial in per_trial for name in trial})
    rewards = [_dimension_scores(t) for t in trials]

    print(f"\n{job.name}  ({len(trials)} trials)")
    for dimension in sorted({k for r in rewards for k in r}):
        values = [r.get(dimension, 0.0) for r in rewards]
        spread = f"{min(values):.3f}-{max(values):.3f}" if len(values) > 1 else ""
        print(f"  {dimension:<10} mean {statistics.fmean(values):.3f}  {spread}")
    if not names:
        return 0
    width = max(len(n) for n in names)
    print(f"  {'criterion':<{width}}  {'mean':>6}  {'min':>5}  {'max':>5}  w")
    for name in names:
        values = [trial.get(name, {}).get("value", 0.0) for trial in per_trial]
        weight = next(
            (t[name]["weight"] for t in per_trial if name in t), 0.0
        )
        mark = "  <-" if statistics.fmean(values) < 1.0 else ""
        print(
            f"  {name:<{width}}  {statistics.fmean(values):>6.3f}  "
            f"{min(values):>5.3f}  {max(values):>5.3f}  {weight:g}{mark}"
        )
    return 0


async def _main(args: argparse.Namespace) -> int:
    if args.command == "report":
        return max(report(Path(job)) for job in args.jobs)
    # A short alias, or any full model id the gateway can pin. The gateway
    # resolves aliases and falls through to the raw string, so a model with
    # provider pins needs no entry in the alias table -- which matters,
    # because that table is Hartwell's *frozen* sign-off set and its length
    # sets that suite's batch economics.
    if args.model not in MODEL_ALIASES and args.model not in MODEL_PROVIDERS:
        raise SystemExit(
            f"no provider pins for {args.model!r}; known: "
            f"{sorted(set(MODEL_ALIASES) | set(MODEL_PROVIDERS))}"
        )
    worst = 0
    for task in args.tasks:
        if not (TASKS / task).is_dir():
            raise SystemExit(f"no such task: {task}")
        job_name = f"ashgrove-{task}-{args.tag}"
        print(f"=== {task} [{args.harness}/{args.model}] k={args.trials}", flush=True)
        worst = max(worst, await _run_one(task, args, job_name))
        report(JOBS / job_name)
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("run", "smoke"):
        p = sub.add_parser(name)
        p.add_argument("tasks", nargs="+")
        p.add_argument("--model", default="opus-5")
        p.add_argument("--harness", choices=("codex", "opencode"), default="codex")
        p.add_argument("--tag", default=None)
        p.add_argument("-k", "--trials", type=int, default=3)
        p.add_argument("-n", "--concurrency", type=int, default=2)

    p = sub.add_parser("report")
    p.add_argument("jobs", nargs="+")

    args = parser.parse_args(argv)
    if args.command == "smoke":
        # One trial, one container: does the agent reach the tools at all?
        args.trials, args.concurrency = 1, 1
    if getattr(args, "tag", None) is None and args.command != "report":
        args.tag = f"{args.harness}-{args.model}"
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())

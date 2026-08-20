"""Run one task against one model tier, k times, through the pinned gateway.

    uv run python scripts/rollout.py --dataset merrick --task <name> \
        --model gpt-5.6-sol --k 9 [--print-config]

Three things this encodes, each of which was learned by getting it wrong.

**k defaults to 9, not 3.** Completion is unreliable on the weaker tiers,
and three samples of a binary outcome cannot distinguish one-in-three
from one-in-nine. One task read 1-of-3 answered at k=3 and 8-of-9 at
k=9 — the sample was the artefact, and a whole account of a model's
behaviour had been built on it.

**The job name carries the tag.** Scores are read back per
`<dataset>-<task>-<tag>` and the aggregator picks the best-sampled job
per model, so a re-sample under its own tag is how a task that *is* in
band stops being reported as out of it.

**The model is pinned to a provider, by a gateway this script owns.** A
bare model id routes to whatever the account's default provider is, which
404s or silently serves different weights. The gateway in
`adapters.harbor_matrix` pins it, and the agent reaches it over
`host.docker.internal`.

Its port is **ephemeral** — bound at start, not configured — so the
config cannot be written until the gateway is up. Hardcoding a port sends
every trial to a dead address, and the whole sweep comes back 0.000:
a harness failure that is indistinguishable downstream from a model that
cannot do the task.

`--print-config` resolves and prints the job without running it, which is
the cheap way to find a bad path or a missing task before a sweep spends
anything.
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

from adapters.harbor_matrix.gateway import (  # noqa: E402
    GatewayConfig,
    ProviderGateway,
)

# What each tier needs on the wire, and which installed agent drives it.
#
# The model name is NOT the same string for both agents, and getting it
# wrong returns `{"error":{"message":"unsupported model"}}` from the
# gateway on the container's first turn — a non-zero exit and a 0.000
# that is not a score.
#
# Codex normalises a slashed id to its last segment before the request
# leaves the container, so `anthropic/claude-opus-5` arrives as
# `claude-opus-5`, which the gateway's alias table does not know. Codex
# therefore gets the bare alias, which survives the normalisation and is
# exactly what the gateway keys on. Hermes does not rewrite the id and
# takes the qualified form.
#
# Read off two job configs that really ran: the codex one scored 1.0 on
# three trials with `opus-5`, the hermes one with `openai/gpt-5.6-sol`.
CODEX = "adapters.harbor_matrix.codex_agent:HartwellCodex"
HERMES = "adapters.harbor_matrix.hermes_agent:HartwellHermes"

TIERS: dict[str, tuple[str, str]] = {
    # alias: (driving agent, model name as that agent must send it)
    "opus-5": (CODEX, "opus-5"),
    "glm-5.2": (CODEX, "glm-5.2"),
    # The codex bridge rejects this tier's payloads outright — "tool exec
    # invoked with incompatible payload", nothing written — so it is
    # driven by hermes instead.
    "gpt-5.6-sol": (HERMES, "openai/gpt-5.6-sol"),
}
MODELS = TIERS  # name kept for the tag/agreement test


def _refuse_unbuilt(task_path: Path, task: str) -> None:
    """Refuse to launch a task the build never finished.

    A directory existing was the only precondition, so a sweep could be
    started against a task with no oracle, no staged environment and no
    grading module beside its criteria. Every trial then runs, the agent
    works, and the score is zero for reasons the model had no part in --
    which is the exact confusion this whole pipeline exists to prevent, paid
    for at k trials times however many models.

    Checked here rather than trusted from the build, because the build and
    the sweep are separate commands run hours apart, and the thing that
    makes them agree should not be somebody's memory.
    """

    required = {
        "oracle": task_path / "tests" / "oracle.json",
        "grading criteria": task_path / "tests" / "criteria.py",
        "shared grading module": task_path / "tests" / "criteria_base.py",
        "staged environment": task_path / "environment",
    }
    absent = sorted(what for what, where in required.items() if not where.exists())
    if absent:
        raise SystemExit(
            f"{task}: not built — missing {absent}. Run the dataset's "
            "build_tasks.py first. Launching now would spend every trial "
            "producing zeros that look like model failure."
        )


def job_config(
    dataset: str,
    task: str,
    model: str,
    tag: str,
    k: int,
    gateway_port: int,
    concurrency: int,
    gateway_token: str = "",
) -> dict:
    task_path = REPO / "datasets" / dataset / "tasks" / task
    if not task_path.is_dir():
        raise SystemExit(f"no task at {task_path}")
    _refuse_unbuilt(task_path, task)
    return {
        "job_name": f"{dataset}-{task}-{tag}",
        "jobs_dir": str(REPO / "jobs"),
        "n_attempts": k,
        # Generous, because a timeout with a deliverable written is an
        # answer, and a timeout with nothing written is a DNF that has to
        # be excluded rather than averaged as a zero. Fewer of both is
        # simply a better measurement.
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
                    "OPENAI_BASE_URL": (
                        f"http://host.docker.internal:{gateway_port}/v1"
                    ),
                    # The agent authenticates to the local gateway with
                    # this, never with the provider key — which stays on
                    # this machine. It reads the value under the name
                    # `OPENAI_API_KEY`, and without it the container's
                    # first turn fails with "Missing environment variable:
                    # OPENAI_API_KEY" and the trial exits non-zero having
                    # produced nothing. That is a harness failure, not a
                    # score.
                    "HARTWELL_GATEWAY_TOKEN": gateway_token,
                },
            }
        ],
        "tasks": [{"path": str(task_path)}],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True, choices=sorted(MODELS))
    parser.add_argument(
        "--k",
        type=int,
        default=9,
        help="attempts; 9 by default because completion is unreliable",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="job suffix; defaults to <model>-k<k> so re-samples do not collide",
    )
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args(argv)

    # The prefix comes from the aggregator's own table, so a job this
    # writes is a job that reader can find. Getting this wrong is silent:
    # the sweep runs and the score is reported as "not run".
    sys.path.insert(0, str(REPO / "scripts"))
    from band import TAG_PREFIX

    tag = args.tag or f"{TAG_PREFIX[args.model]}-k{args.k}"
    if args.print_config:
        # A placeholder port, because there is no gateway to ask. This
        # path exists to check the task path and the schema, not to be run.
        print(
            json.dumps(
                job_config(
                    args.dataset,
                    args.task,
                    args.model,
                    tag,
                    args.k,
                    0,
                    args.concurrency,
                ),
                indent=2,
            )
        )
        return 0

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit(
            "OPENROUTER_API_KEY is not set; the gateway cannot pin a provider "
            "without it and every trial would fail identically"
        )

    token = secrets.token_urlsafe(24)

    async def run() -> int:
        gateway = ProviderGateway(
            GatewayConfig(
                openrouter_api_key=key,
                gateway_token=token,
                bind_host="0.0.0.0",
                port=0,
            )
        )
        async with gateway:
            config = job_config(
                args.dataset,
                args.task,
                args.model,
                tag,
                args.k,
                gateway.port,
                args.concurrency,
                gateway_token=token,
            )
            out = REPO / "jobs" / f"{config['job_name']}.config.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(config, indent=2), encoding="utf-8")
            print(f"gateway on :{gateway.port}  config -> {out}")
            print(f"running {config['job_name']} at k={args.k}")
            # Harbor runs in its own tool environment, where this repo
            # is not installed. It imports the driving agent by module
            # path, so `src` has to be on the PYTHONPATH it inherits —
            # the matrix runner does this for subprocesses it spawns, and
            # invoking `harbor` directly skips that entirely.
            #
            # Found by running it, not by reading it: an import check with
            # PYTHONPATH set by hand passes and proves nothing about what
            # the child actually inherits. Without this the job dies at
            # "No module named 'adapters'" before a single trial starts.
            environment = os.environ.copy()
            roots = [str(REPO / "src")]
            if inherited := environment.get("PYTHONPATH"):
                roots.extend(inherited.split(os.pathsep))
            environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(roots))
            return await asyncio.to_thread(
                subprocess.call,
                ["harbor", "run", "-c", str(out)],
                env=environment,
            )

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())

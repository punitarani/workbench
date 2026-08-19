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

**The model is pinned to a provider.** A bare model id routes to whatever
the account's default provider is, which 404s or silently serves
different weights. The gateway in `adapters.harbor_matrix` exists for
this, and the agent reaches it over `host.docker.internal`.

`--print-config` resolves and prints the job without running it, which is
the cheap way to find a bad path or a missing task before a sweep spends
anything.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Alias -> the provider-qualified id the gateway pins.
MODELS = {
    "opus-5": "anthropic/claude-opus-5",
    "gpt-5.6-sol": "openai/gpt-5.6-sol",
    "glm-5.2": "z-ai/glm-5.2",
}

# Which installed agent drives the container for which model. The codex
# bridge rejects some payloads outright — "tool exec invoked with
# incompatible payload", nothing written, a 0.000 that is not a score —
# so the tier that hits it uses the hermes agent instead.
AGENTS = {
    "gpt-5.6-sol": "adapters.harbor_matrix.hermes_agent:HartwellHermes",
    "opus-5": "adapters.harbor_matrix.codex_agent:HartwellCodex",
    "glm-5.2": "adapters.harbor_matrix.codex_agent:HartwellCodex",
}

DEFAULT_GATEWAY_PORT = 50341


def job_config(
    dataset: str,
    task: str,
    model: str,
    tag: str,
    k: int,
    gateway_port: int,
    concurrency: int,
) -> dict:
    task_path = REPO / "datasets" / dataset / "tasks" / task
    if not task_path.is_dir():
        raise SystemExit(f"no task at {task_path}")
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
                "name": AGENTS[model],
                "model_name": MODELS[model],
                "n_concurrent": concurrency,
                "extra_allowed_hosts": ["host.docker.internal"],
                "env": {
                    "OPENAI_BASE_URL": (
                        f"http://host.docker.internal:{gateway_port}/v1"
                    )
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
    parser.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args(argv)

    # The prefix comes from the aggregator's own table, so a job this
    # writes is a job that reader can find. Getting this wrong is silent:
    # the sweep runs and the score is reported as "not run".
    sys.path.insert(0, str(REPO / "scripts"))
    from band import TAG_PREFIX

    tag = args.tag or f"{TAG_PREFIX[args.model]}-k{args.k}"
    config = job_config(
        args.dataset,
        args.task,
        args.model,
        tag,
        args.k,
        args.gateway_port,
        args.concurrency,
    )
    if args.print_config:
        print(json.dumps(config, indent=2))
        return 0

    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit(
            "OPENROUTER_API_KEY is not set; the gateway cannot pin a provider "
            "without it and every trial would fail identically"
        )

    out = REPO / "jobs" / f"{config['job_name']}.config.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"config -> {out}")
    print(f"running {config['job_name']} at k={args.k}")
    return subprocess.call(["harbor", "run", "-c", str(out)])


if __name__ == "__main__":
    sys.exit(main())

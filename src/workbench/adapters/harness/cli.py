"""Best-of-N eval of one model against one Harbor task.

    OPENROUTER_API_KEY=... uv run python -m workbench.adapters.harness.cli \\
        --task datasets/legal-nda/tasks/vantage-triage \\
        --model deepseek/deepseek-v4-flash-0731 --attempts 3

Each attempt copies the task's built environment bundle to a fresh run
directory, runs one episode inside the bundle's ``workspace/``, and grades
it with the task's own grader.
"""

import argparse
import asyncio
import os
import shutil
import tempfile
import tomllib
from pathlib import Path

from workbench.adapters.harness.agent_loop import run_episode
from workbench.adapters.harness.grade import grade_episode
from workbench.adapters.harness.openrouter_client import (
    MODEL_PROVIDERS,
    OpenRouterChatClient,
)


def _prices(text: str) -> tuple[float, float]:
    prompt_price, completion_price = (float(part) for part in text.split(","))
    return prompt_price, completion_price


def read_call_budget(task_dir: Path) -> int | None:
    """The task's tool-call cap from ``[harness] max_tool_calls`` in
    task.toml; tasks without the key keep unlimited calls."""
    manifest = task_dir / "task.toml"
    if not manifest.is_file():
        return None
    value = (
        tomllib.loads(manifest.read_text(encoding="utf-8"))
        .get("harness", {})
        .get("max_tool_calls")
    )
    return None if value is None else int(value)


async def _run(args: argparse.Namespace, api_key: str) -> None:
    task_dir: Path = args.task
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    max_tool_calls = read_call_budget(task_dir)
    if max_tool_calls is not None:
        print(f"call budget: {max_tool_calls} tool calls")
    client = OpenRouterChatClient(
        api_key,
        args.model,
        temperature=args.temperature,
        providers=(
            tuple(p for p in args.provider.split(",") if p)
            if args.provider
            else MODEL_PROVIDERS.get(args.model, ())
        ),
    )
    scores: list[float] = []
    try:
        with tempfile.TemporaryDirectory(prefix="harness-") as runs_dir:
            for attempt in range(1, args.attempts + 1):
                run_dir = Path(runs_dir) / f"attempt-{attempt:02d}"
                shutil.copytree(task_dir / "bundle", run_dir)
                prompt_before = client.prompt_tokens
                completion_before = client.completion_tokens
                episode = await run_episode(
                    run_dir / "workspace",
                    instruction,
                    client,
                    max_turns=args.max_turns,
                    max_tokens_per_call=args.max_tokens,
                    max_tool_calls=max_tool_calls,
                )
                reward = grade_episode(task_dir, run_dir)
                scores.append(float(reward["score"]))
                if args.keep_transcripts is not None:
                    args.keep_transcripts.mkdir(parents=True, exist_ok=True)
                    safe_model = args.model.replace("/", "_")
                    (
                        args.keep_transcripts
                        / f"{task_dir.name}-{safe_model}-a{attempt}.json"
                    ).write_text(episode.model_dump_json(indent=2), encoding="utf-8")
                print(
                    f"attempt {attempt}: score={reward['score']:.4f} "
                    f"stop={episode.stop_reason} turns={episode.turns} "
                    f"tool_calls={episode.tool_calls} tokens="
                    f"{client.prompt_tokens - prompt_before}p+"
                    f"{client.completion_tokens - completion_before}c"
                )
    finally:
        await client.aclose()
    print(f"best-of-{len(scores)}: {max(scores):.4f}")
    print(
        f"total tokens: prompt={client.prompt_tokens} "
        f"completion={client.completion_tokens}"
    )
    if args.prices is not None:
        print(f"estimated cost: ${client.usage_cost(args.prices):.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m workbench.adapters.harness.cli",
        description="Best-of-N eval of one model against one Harbor task.",
    )
    parser.add_argument("--task", type=Path, required=True, help="task directory")
    parser.add_argument("--model", required=True, help="OpenRouter model id")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument(
        "--keep-transcripts",
        type=Path,
        default=None,
        help="persist each attempt's transcript JSON into this directory",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="comma-separated provider slugs, in priority order, to pin "
        "routing to (no fallbacks); defaults to MODEL_PROVIDERS for known "
        "models, unpinned otherwise",
    )
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument(
        "--prices",
        type=_prices,
        default=None,
        metavar="PROMPT,COMPLETION",
        help="USD per Mtok, to print an estimated cost",
    )
    args = parser.parse_args(argv)
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    if not (args.task / "bundle").is_dir():
        parser.error(f"no built environment bundle under {args.task}")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        parser.error("OPENROUTER_API_KEY is not set")
    asyncio.run(_run(args, api_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

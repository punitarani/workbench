"""Run a workplace demo day: record against OpenRouter or replay a cassette.

    uv run python -m workbench.simulation.demo --seed 42 --out out/legal-day \
        --mode replay \
        --cassette src/workbench/workplaces/legal/cassettes/day-seed42

Record mode needs OPENROUTER_API_KEY and writes the cassette it runs from;
replay mode needs no network and is byte-deterministic.
"""

import argparse
import asyncio
import importlib
import os
import signal
import sys
from pathlib import Path

from workbench.core.seed import Seed
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from workbench.simulation.lm.openrouter import DEFAULT_MODEL, OpenRouterLM
from workbench.simulation.lm.protocol import LanguageModel
from workbench.simulation.run import resume_workplace, run_workplace
from workbench.simulation.workplace.spec import WorkplaceSpec

DEFAULT_WORKPLACE = "workbench.workplaces.legal:WORKPLACE"


def load_workplace(ref: str) -> WorkplaceSpec:
    module_name, _, attribute = ref.partition(":")
    module = importlib.import_module(module_name)
    spec = getattr(module, attribute)
    if not isinstance(spec, WorkplaceSpec):
        raise SystemExit(f"{ref} is not a WorkplaceSpec")
    return spec


def build_lm(mode: str, cassette: Path, model: str, max_calls: int) -> LanguageModel:
    store = CassetteStore(cassette)
    if mode == "replay":
        return ReplayLM(store)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("record mode requires OPENROUTER_API_KEY")
    backend = OpenRouterLM(api_key=api_key)
    return BudgetedLM(RecordingLM(backend, store), max_calls=max_calls)


def _clock_seconds(clock: str) -> int:
    hours, _, minutes = clock.partition(":")
    return int(hours) * 3600 + int(minutes) * 60


async def _run(args: argparse.Namespace) -> int:
    spec = load_workplace(args.workplace)
    inner = build_lm(args.mode, args.cassette, args.model, args.max_calls)

    interrupted = False

    def request_stop() -> None:
        nonlocal interrupted
        if interrupted:
            raise SystemExit(130)
        interrupted = True
        print(
            "\ninterrupt: finishing the current step, committing, then "
            "stopping (press again to abort hard)"
        )

    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, request_stop)

    end_time = (
        _clock_seconds(args.until) if args.until else _clock_seconds(spec.end_of_day)
    )
    stop = StopCondition(
        end_time=end_time,
        max_steps=args.max_steps,
        stop_requested=lambda: interrupted,
    )

    if args.resume:
        result = await resume_workplace(
            spec,
            out_dir=args.out,
            inner_lm=inner,
            model=args.model,
            stop=stop,
        )
    else:
        result = await run_workplace(
            spec,
            seed=Seed(root=args.seed),
            out_dir=args.out,
            inner_lm=inner,
            model=args.model,
            stop=stop,
        )
    print(
        f"run finished: {result.steps} steps, reason={result.reason}, "
        f"final_time={result.final_time}s"
    )
    if result.reason == "interrupted":
        print(f"resume with: --resume --out {args.out}")
    print(f"world log: {args.out / 'world.jsonl'}")
    print(f"manifest:  {args.out / 'manifest.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    parser.add_argument("--cassette", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--workplace", default=DEFAULT_WORKPLACE)
    parser.add_argument("--max-calls", type=int, default=800)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="continue the run in --out from its latest committed step",
    )
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument(
        "--until", default=None, help='stop at this simulated clock, e.g. "13:00"'
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

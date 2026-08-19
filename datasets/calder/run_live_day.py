"""Record or replay the Calder live day — Monday 2026-07-20 — as a
hybrid continuation of the six-month chronicle.

    uv run --env-file .env python datasets/calder/run_live_day.py \\
        --mode record --window 8 --out out/calder/live

Record mode needs OPENROUTER_API_KEY and writes the cassette it runs
from; replay mode needs no network and is byte-deterministic. The world
log in --out contains the full history plus the live day; metrics land
next to it as ``live-metrics-<mode>-w<window>.json``.
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.chronicle.minter import minter_from_events
from simulation.engine.engine import StopCondition
from simulation.lm.budget import BudgetedLM
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.lm.openrouter import OpenRouterLM
from simulation.lm.protocol import LanguageModel
from simulation.lm.retry import RetryLM
from simulation.run import resume_workplace, run_compiled
from simulation.workplace.compile import compile_workplace
from workplaces.calder import LIVE_DAY_OFFSET
from workplaces.calder.spec import LIVE_DAY_SPEC

DEFAULT_HISTORY = Path("out/calder/world.jsonl")
DEFAULT_CASSETTE = Path("src/workplaces/calder/cassettes/live-2026-07-20")
# The model the cassette is recorded against; cassette keys include the
# model string, so record and replay must agree. The provider list matters
# only while recording: OpenRouterLM defaults to an openai-only order,
# which can never serve a deepseek model, and a single provider's shared
# pool rate-limits under load — the ordered list is the fallback chain.
CASSETTE_MODEL = "deepseek/deepseek-v4-flash-0731"
CASSETTE_PROVIDERS = ("deepinfra", "fireworks", "novita", "deepseek")


def build_lm(
    mode: str, cassette: Path, max_calls: int
) -> tuple[LanguageModel, OpenRouterLM | None]:
    store = CassetteStore(cassette)
    if mode == "replay":
        return ReplayLM(store), None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("record mode requires OPENROUTER_API_KEY")
    backend = OpenRouterLM(api_key=api_key, providers=CASSETTE_PROVIDERS)
    lm = BudgetedLM(RecordingLM(RetryLM(backend), store), max_calls=max_calls)
    return lm, backend


async def _run(args: argparse.Namespace) -> int:
    if not args.history.exists():
        raise SystemExit(
            f"{args.history} is missing; build it first: "
            "uv run python datasets/calder/build_history.py --days all"
        )
    if not args.resume and (args.out / "run.db").exists():
        raise SystemExit(
            f"{args.out / 'run.db'} already exists; remove the directory or "
            "pass --resume"
        )

    history = tuple(read_events(args.history))
    compiled = compile_workplace(
        LIVE_DAY_SPEC,
        Seed(root=args.seed),
        time_offset=LIVE_DAY_OFFSET,
        starting_minter=minter_from_events(history),
        include_genesis=False,
    )
    inner, backend = build_lm(args.mode, args.cassette, args.max_calls)

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
    stop = StopCondition(
        end_time=compiled.end_time,
        max_steps=args.max_steps,
        stop_requested=lambda: interrupted,
    )

    started = time.perf_counter()
    try:
        if args.resume:
            result = await resume_workplace(
                LIVE_DAY_SPEC,
                out_dir=args.out,
                inner_lm=inner,
                model=args.model,
                stop=stop,
                checkpoint_every=args.checkpoint_every,
                window=args.window,
            )
        else:
            result = await run_compiled(
                compiled,
                seed=Seed(root=args.seed),
                out_dir=args.out,
                inner_lm=inner,
                model=args.model,
                stop=stop,
                history=history,
                checkpoint_every=args.checkpoint_every,
                window=args.window,
            )
    finally:
        if backend is not None:
            await backend.close()
    wall = time.perf_counter() - started

    combined = tuple(read_events(args.out / "world.jsonl"))
    report = validate_events(combined)
    new_events = len(combined) - len(history)

    metrics: dict[str, object] = {
        "mode": args.mode,
        "window": args.window,
        "model": args.model,
        "seed": args.seed,
        "steps": result.steps,
        "reason": result.reason,
        "final_time": result.final_time,
        "wall_seconds": round(wall, 2),
        "steps_per_second": round(result.steps / wall, 3) if wall else None,
        "history_events": len(history),
        "new_events": new_events,
        "total_events": len(combined),
        "validates": report.ok,
        "world_bytes": (args.out / "world.jsonl").stat().st_size,
        "run_db_bytes": (args.out / "run.db").stat().st_size,
    }
    if isinstance(inner, BudgetedLM):
        metrics["lm_calls"] = inner.calls
        metrics["prompt_tokens"] = inner.usage.prompt_tokens
        metrics["completion_tokens"] = inner.usage.completion_tokens
    metrics_path = args.out / f"live-metrics-{args.mode}-w{args.window}.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(
        f"live day: {result.steps} steps, reason={result.reason}, "
        f"{new_events} new events in {wall:.1f}s "
        f"(validates={report.ok})"
    )
    print(f"metrics -> {metrics_path}")
    if result.reason == "interrupted":
        print(f"resume with: --resume --out {args.out}")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--out", type=Path, default=Path("out/calder/live"))
    parser.add_argument("--mode", choices=("record", "replay"), default="replay")
    parser.add_argument("--cassette", type=Path, default=DEFAULT_CASSETTE)
    parser.add_argument("--model", default=CASSETTE_MODEL)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--max-calls", type=int, default=3000)
    parser.add_argument("--checkpoint-every", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

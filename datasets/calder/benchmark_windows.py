"""Windowed-engine benchmark on the recorded Calder live day.

Replays the committed cassette at several window sizes with per-call LM
latency modeled at a measured figure (cassette hits return instantly, so
without the delay both replays finish in engine-overhead time and the
comparison would measure nothing). Also probes admission batch sizes so
the report can say how much same-time parallelism the day actually held.

    uv run python datasets/calder/benchmark_windows.py \\
        [--latency 5.0] [--windows 1,8] [--out out/calder/bench]
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from core.seed import Seed
from core.worldlog import read_events
from simulation.chronicle.minter import minter_from_events
from simulation.engine.engine import InterruptEngine, StopCondition
from simulation.lm.cassette import CassetteStore, ReplayLM
from simulation.lm.protocol import LMRequest, LMResponse
from simulation.run import run_compiled
from simulation.workplace.compile import compile_workplace
from workplaces.calder import LIVE_DAY_OFFSET
from workplaces.calder.spec import LIVE_DAY_SPEC

DEFAULT_HISTORY = Path("out/calder/world.jsonl")
CASSETTE = Path("src/workplaces/calder/cassettes/live-2026-07-20")
MODEL = "deepseek/deepseek-v4-flash-0731"


class DelayedReplayLM:
    """Cassette replay with modeled per-call latency: what the live run
    would cost if every call took exactly ``latency`` seconds."""

    def __init__(self, store: CassetteStore, latency: float) -> None:
        self._inner = ReplayLM(store)
        self._latency = latency
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        self.calls += 1
        await asyncio.sleep(self._latency)
        return await self._inner.complete(request)


async def _bench(history: tuple, *, window: int, latency: float, out_dir: Path) -> dict:
    compiled = compile_workplace(
        LIVE_DAY_SPEC,
        Seed(root=42),
        time_offset=LIVE_DAY_OFFSET,
        starting_minter=minter_from_events(history),
        include_genesis=False,
    )
    lm = DelayedReplayLM(CassetteStore(CASSETTE), latency)

    sizes: list[int] = []
    original = InterruptEngine.step_batch

    async def probed(self, allowance):
        results = await original(self, allowance)
        sizes.append(len(results))
        return results

    InterruptEngine.step_batch = probed
    try:
        started = time.perf_counter()
        result = await run_compiled(
            compiled,
            seed=Seed(root=42),
            out_dir=out_dir,
            inner_lm=lm,
            model=MODEL,
            stop=StopCondition(end_time=compiled.end_time),
            history=history,
            checkpoint_every=50,
            window=window,
        )
        wall = time.perf_counter() - started
    finally:
        InterruptEngine.step_batch = original

    return {
        "window": window,
        "modeled_latency_seconds": latency,
        "steps": result.steps,
        "reason": result.reason,
        "lm_calls": lm.calls,
        "wall_seconds": round(wall, 2),
        "batches": len(sizes) if sizes else None,
        "max_batch": max(sizes) if sizes else None,
        "multi_step_batches": sum(1 for s in sizes if s > 1) if sizes else None,
        "world_sha_bytes": (out_dir / "world.jsonl").stat().st_size,
    }


async def _main(args: argparse.Namespace) -> int:
    history = tuple(read_events(args.history))
    windows = [int(w) for w in args.windows.split(",")]
    rows = []
    reference: bytes | None = None
    for window in windows:
        out_dir = args.out / f"w{window}"
        rows.append(
            await _bench(history, window=window, latency=args.latency, out_dir=out_dir)
        )
        produced = (out_dir / "world.jsonl").read_bytes()
        if reference is None:
            reference = produced
        elif produced != reference:
            print("FATAL: window sizes produced different worlds", file=sys.stderr)
            return 1
        print(json.dumps(rows[-1]))
    if len(rows) >= 2 and rows[0]["window"] == 1:
        for row in rows[1:]:
            row["speedup_vs_w1"] = round(
                rows[0]["wall_seconds"] / row["wall_seconds"], 2
            )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "bench.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    print(f"bench -> {args.out / 'bench.json'}")
    print("all windows byte-identical:", reference is not None)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--out", type=Path, default=Path("out/calder/bench"))
    parser.add_argument("--latency", type=float, default=5.0)
    parser.add_argument("--windows", default="1,8")
    args = parser.parse_args(argv)
    if any((args.out / f"w{w}").exists() for w in args.windows.split(",")):
        raise SystemExit(f"{args.out} already holds results; remove it first")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())

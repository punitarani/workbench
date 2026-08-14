"""The Calder epoch runner: LLM-first simulation from day zero.

    uv run --env-file .env python datasets/calder/run_epoch.py start \\
        --days 5 --mode record --out out/calder/epoch

Subcommands:
  start   begin a fresh run (record needs OPENROUTER_API_KEY)
  resume  continue an interrupted run from its committed state
  status  one-screen view of a running or finished run
  audit   realism gates over the produced world log
  report  markdown summary from telemetry + the log

Per-day telemetry lands in ``telemetry.jsonl`` beside ``run.db``; every
day ends with a checkpoint, so a kill at any point resumes cleanly.
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path

from workbench.core.seed import Seed
from workbench.core.store import SqliteRunStore
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from workbench.simulation.lm.openrouter import OpenRouterLM
from workbench.simulation.lm.retry import RetryLM
from workbench.simulation.run import resume_workplace, run_compiled
from workbench.simulation.telemetry import DayRow, SegmentRow, TelemetryWriter
from workbench.simulation.workplace.compile import compile_workplace
from workbench.workplaces.calder.epoch import epoch_director, epoch_spec

FAST_MODEL = "deepseek/deepseek-v4-flash-0731"
DEEP_MODEL = "anthropic/claude-haiku-4.5"
PROVIDERS = ("deepinfra", "fireworks", "novita", "deepseek")
DEFAULT_CASSETTE = Path("src/workbench/workplaces/calder/cassettes/epoch-seed42")


def build_lm(mode: str, cassette: Path, max_calls: int):
    store = CassetteStore(cassette)
    if mode == "replay":
        return ReplayLM(store), None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("record mode requires OPENROUTER_API_KEY")
    backend = OpenRouterLM(
        api_key=api_key,
        providers=PROVIDERS,
        providers_by_model={DEEP_MODEL: ("amazon-bedrock",)},
        max_concurrency=16,
    )
    return BudgetedLM(
        RecordingLM(RetryLM(backend), store), max_calls=max_calls
    ), backend


class _DayTracker:
    """Accumulates per-day telemetry through on_step/on_batch."""

    def __init__(self, writer: TelemetryWriter, budget: BudgetedLM | None) -> None:
        self._writer = writer
        self._budget = budget
        self._day = ""
        self._day_index = -1
        self._steps = 0
        self._events: Counter[str] = Counter()
        self._batches: list[int] = []
        self._calls_base = 0
        self._network_base = 0
        self._tokens_base = (0, 0)
        self._wall_base = time.perf_counter()

    def on_batch(self, results) -> None:
        self._batches.append(len(results))

    def on_step(self, result) -> None:
        event = result.event
        if event.tag == "sim.day.started":
            self._day = event.payload.day
            self._day_index += 1
            self._reset_counters()
        self._steps += 1
        self._events[event.tag] += 1
        if event.tag == "sim.day.ended":
            self._flush()

    def _reset_counters(self) -> None:
        self._steps = 0
        self._events = Counter()
        self._batches = []
        self._wall_base = time.perf_counter()
        if self._budget is not None:
            self._calls_base = self._budget.calls
            self._network_base = self._budget.network_calls
            self._tokens_base = (
                self._budget.usage.prompt_tokens,
                self._budget.usage.completion_tokens,
            )

    def _flush(self) -> None:
        calls = network = prompt = completion = 0
        if self._budget is not None:
            calls = self._budget.calls - self._calls_base
            network = self._budget.network_calls - self._network_base
            prompt = self._budget.usage.prompt_tokens - self._tokens_base[0]
            completion = self._budget.usage.completion_tokens - self._tokens_base[1]
        self._writer.append(
            DayRow(
                day=self._day,
                day_index=max(0, self._day_index),
                steps=self._steps,
                events=dict(self._events),
                lm_calls=calls,
                lm_network_calls=network,
                prompt_tokens=prompt,
                completion_tokens=completion,
                rejections=self._events.get("sim.gm.note", 0),
                batches=len(self._batches),
                max_batch=max(self._batches, default=0),
                wall_seconds=round(time.perf_counter() - self._wall_base, 2),
            )
        )


async def _start_or_resume(args: argparse.Namespace, *, resume: bool) -> int:
    seed = Seed(root=args.seed)
    spec = epoch_spec(days=args.days)
    compiled = compile_workplace(spec, seed)
    director = epoch_director(seed)
    inner, backend = build_lm(args.mode, args.cassette, args.max_calls)
    writer = TelemetryWriter(args.out / "telemetry.jsonl")
    tracker = _DayTracker(writer, inner if isinstance(inner, BudgetedLM) else None)

    if not resume and (args.out / "run.db").exists():
        raise SystemExit(f"{args.out / 'run.db'} exists; use resume or a new --out")

    interrupted = False

    def request_stop() -> None:
        nonlocal interrupted
        if interrupted:
            raise SystemExit(130)
        interrupted = True
        print("\ninterrupt: committing the current step, then stopping")

    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, request_stop)
    stop = StopCondition(
        end_time=compiled.end_time,
        max_steps=args.max_steps,
        stop_requested=lambda: interrupted,
    )

    started = time.perf_counter()
    try:
        common = dict(
            inner_lm=inner,
            model=FAST_MODEL,
            deep_model=DEEP_MODEL,
            director=director,
            stop=stop,
            checkpoint_every=args.checkpoint_every,
            window=args.window,
            on_step=tracker.on_step,
            on_batch=tracker.on_batch,
        )
        if resume:
            result = await resume_workplace(spec, out_dir=args.out, **common)
        else:
            result = await run_compiled(compiled, seed=seed, out_dir=args.out, **common)
    finally:
        if backend is not None:
            await backend.close()
    wall = time.perf_counter() - started

    writer.append(
        SegmentRow(
            label="resume" if resume else "start",
            day=tracker._day or None,
            steps=result.steps,
            reason=result.reason,
        )
    )
    events = tuple(read_events(args.out / "world.jsonl"))
    ok = validate_events(events).ok
    print(
        f"epoch segment: {result.steps} steps, reason={result.reason}, "
        f"{len(events)} events, {wall:.1f}s wall, validates={ok}"
    )
    if isinstance(inner, BudgetedLM):
        print(
            f"lm: {inner.calls} calls ({inner.network_calls} network), "
            f"{inner.usage.prompt_tokens}p/{inner.usage.completion_tokens}c tokens"
        )
    if result.reason == "interrupted":
        print(f"resume with: run_epoch.py resume --out {args.out} --days {args.days}")
    return 0 if ok else 1


def _status(args: argparse.Namespace) -> int:
    store = SqliteRunStore.open(args.out / "run.db")
    head_seq, head_time = store.head()
    step = store.get_meta("step")
    store.close()
    day, clock = divmod(head_time, 86_400)
    print(
        f"head: seq {head_seq}, step {step}, sim day {day} "
        f"{clock // 3600:02d}:{(clock % 3600) // 60:02d}"
    )
    telemetry = args.out / "telemetry.jsonl"
    if telemetry.exists():
        lines = telemetry.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-4:]:
            row = json.loads(line)
            if row.get("kind") == "day":
                print(
                    f"  {row['day']}: {row['steps']} steps, "
                    f"{row['lm_calls']} calls, max batch {row['max_batch']}, "
                    f"{row['wall_seconds']}s"
                )
    return 0


def audit(log_path: Path) -> int:
    events = tuple(read_events(log_path))
    failures = 0

    def check(label: str, passed: bool) -> None:
        nonlocal failures
        print(f"  [{'ok' if passed else 'FAIL'}] {label}")
        if not passed:
            failures += 1

    report = validate_events(events)
    check("world log validates", report.ok)

    days = [e for e in events if e.tag == "sim.day.started"]
    acts = [
        e
        for e in events
        if e.tag
        in ("email.message", "chat.message", "ticket.commented", "work.time.logged")
    ]
    notes = [e for e in events if e.tag == "sim.gm.note"]
    braked = [e for e in notes if "already carries" in e.payload.note]
    failures = [e for e in notes if "already carries" not in e.payload.note]
    check(
        f"grounding failures {len(failures)}/{len(acts)} stay under 20% "
        f"({len(braked)} thread-cap brakes counted separately)",
        len(acts) > 0 and len(failures) <= 0.2 * len(acts),
    )
    plans = Counter(e.payload.day for e in events if e.tag == "sim.agent.plan")
    reflections = Counter(e.payload.day for e in events if e.tag == "sim.agent.memory")
    check(
        f"every workday carries plans ({len(plans)}/{len(days)} days)",
        len(plans) == len(days),
    )
    check(
        f"every workday carries reflections ({len(reflections)}/{len(days)})",
        len(reflections) == len(days),
    )
    mail = [e.payload.body for e in events if e.tag == "email.message"]
    if mail:
        check(
            f"mail bodies {len(set(mail))}/{len(mail)} distinct (>=80%)",
            len(set(mail)) >= 0.8 * len(mail),
        )
    threads: Counter[str] = Counter(
        e.payload.thread_id for e in events if e.tag == "email.message"
    )
    check(
        f"no thread exceeds 12 messages (max {max(threads.values(), default=0)})",
        max(threads.values(), default=0) <= 12,
    )
    cues = [e for e in events if e.tag == "sim.cue"]
    check(f"the world stirred ({len(cues)} cues)", len(cues) > 0)
    transcripts = [e for e in events if e.tag == "meeting.transcript"]
    # Seed meetings convene once (recurrence is future work), so the gate
    # is per-run, not per-day.
    check(
        f"meetings happened ({len(transcripts)} transcripts)",
        len(transcripts) >= 1,
    )
    return failures


def _report(args: argparse.Namespace) -> int:
    events = tuple(read_events(args.out / "world.jsonl"))
    tags = Counter(e.tag for e in events)
    print("# Calder epoch report\n")
    print(f"Events: {len(events)}")
    for tag, count in tags.most_common():
        print(f"- {tag}: {count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=Path("out/calder/epoch"))
        p.add_argument("--days", type=int, default=5)
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--mode", choices=("record", "replay"), default="record")
        p.add_argument("--cassette", type=Path, default=DEFAULT_CASSETTE)
        p.add_argument("--window", type=int, default=32)
        p.add_argument("--max-calls", type=int, default=100_000)
        p.add_argument("--checkpoint-every", type=int, default=100)
        p.add_argument("--max-steps", type=int, default=None)
    for name in ("status", "report"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=Path("out/calder/epoch"))
    p = sub.add_parser("audit")
    p.add_argument("--out", type=Path, default=Path("out/calder/epoch"))
    args = parser.parse_args(argv)

    if args.command in ("start", "resume"):
        return asyncio.run(_start_or_resume(args, resume=args.command == "resume"))
    if args.command == "status":
        return _status(args)
    if args.command == "audit":
        return audit(args.out / "world.jsonl")
    return _report(args)


if __name__ == "__main__":
    sys.exit(main())

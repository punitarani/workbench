"""The Merrick Stanton epoch runner: six months of a law firm.

Same engine and CLI as the accounting firms, three differences that
matter:

**Bigger tiers.** The fast model writes roughly nine calls in ten — every
email, chat message and document — so it is the tier that decides what
the world reads like, not a background detail. It moves up to Sonnet
here, with Opus on the deep path that plans and reflects.

**Higher concurrency.** Recording is latency-bound rather than
token-bound: the ten-day accounting run averaged 500 calls in 18 minutes
at 16-way concurrency, which is about 35 seconds of wall time per call
and almost all of it waiting. Six months is thirteen times that run, so
the concurrency is what decides whether the window is a day or a week.

**A resumable long run.** Every day ends with a checkpoint, so a kill at
any point resumes cleanly — which is a requirement rather than a
convenience over a window this long.

    uv run --env-file .env python datasets/merrick/run_epoch.py start \\
        --days 180 --mode record --out out/merrick/epoch

Subcommands:
  start   begin a fresh run (record needs OPENROUTER_API_KEY)
  resume  continue an interrupted run from its committed state
  status  one-screen view of a running or finished run
  audit   realism gates over the produced world log
  report  markdown summary from telemetry + the log
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

from core.seed import Seed
from core.store import SqliteRunStore
from core.worldlog import read_events, validate_events
from simulation.engine.engine import StopCondition
from simulation.lm.budget import BudgetedLM
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.lm.openrouter import OpenRouterLM
from simulation.lm.retry import RetryLM
from simulation.run import resume_workplace, run_compiled
from simulation.telemetry import DayRow, SegmentRow, TelemetryWriter
from simulation.workplace.compile import compile_workplace
from workplaces.merrick.epoch import epoch_director, epoch_spec

# The fast tier writes the world: every email, every chat message, every
# document body. It is not a background detail and it is not where to
# save money -- it is the tier that decides whether the corpus reads like
# a law firm. Deep handles planning and reflection, roughly one call in
# ten.
FAST_MODEL = "anthropic/claude-sonnet-5"
# Sonnet on both tiers, not Opus on deep. A cohort's wall time is its
# *slowest* call, so a tier used by one call in ten still sets the pace
# for the other nine -- and the deep tier plans and reflects, while the
# fast tier writes every word of the world. The upgrade that buys fidelity
# is the fast one, and it is kept.
DEEP_MODEL = "anthropic/claude-sonnet-5"
# Direct `anthropic` is blocked on this key and 404s rather than falling
# back, so both tiers route through Bedrock, which serves the same weights.
PROVIDERS = ("amazon-bedrock",)
# Recording is latency-bound, not token-bound. Raising this is what makes
# a six-month window finish in a night instead of a week; it is passed
# through so a rate-limited key can drop it without a code change.
# Personas wake in cohorts and the whole cast wakes together, so useful
# concurrency is the cohort width -- measured at exactly 21, the internal
# headcount. Anything above that is provisioned for nothing.
DEFAULT_CONCURRENCY = 24
DEFAULT_CASSETTE = Path("out/merrick/cassette")


def build_lm(
    mode: str, cassette: Path, max_calls: int, concurrency: int = DEFAULT_CONCURRENCY
):
    store = CassetteStore(cassette)
    if mode == "replay":
        return ReplayLM(store), None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("record mode requires OPENROUTER_API_KEY")
    backend = OpenRouterLM(
        api_key=api_key,
        providers=PROVIDERS,
        providers_by_model={FAST_MODEL: PROVIDERS, DEEP_MODEL: PROVIDERS},
        max_concurrency=concurrency,
    )
    return BudgetedLM(
        RecordingLM(RetryLM(backend), store), max_calls=max_calls
    ), backend


def _days_recorded(telemetry: Path) -> int:
    """How many days this run has already written, for a resume to continue.

    Counts distinct `day` dates rather than rows: a run killed between
    `sim.day.started` and `sim.day.ended` writes no row for that day, and a
    row count would then be right by accident; a date count is right on
    purpose. A malformed line is skipped rather than fatal — this is
    telemetry, and refusing to resume a 20-hour recording over a truncated
    JSON line would be the cure being worse.
    """

    if not telemetry.is_file():
        return 0
    seen: set[str] = set()
    for line in telemetry.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "day" and row.get("day"):
            seen.add(row["day"])
    return len(seen)


class _DayTracker:
    """Accumulates per-day telemetry through on_step/on_batch."""

    def __init__(
        self,
        writer: TelemetryWriter,
        budget: BudgetedLM | None,
        *,
        days_already_recorded: int = 0,
    ) -> None:
        self._writer = writer
        self._budget = budget
        self._day = ""
        # Continues the count across a resume. It used to start at -1
        # unconditionally, so a run stopped at day 13 and resumed wrote its
        # next day as `day_index` 0 — silently, into a file whose whole
        # purpose is per-day analysis. Every band, rate and trend keyed on
        # `day_index` is then wrong for a resumed run, and nothing says so:
        # the `day` date field stays correct, so the rows look fine one at
        # a time and only the sequence is broken.
        self._day_index = days_already_recorded - 1
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
    if resume:
        # A resume must recompile the spec the run was started with, and
        # `--days` is part of it. Left to the flag's default a fifteen-day
        # run resumes as a five-day one, the config hash moves, and the
        # run refuses to continue — correctly, but after the operator has
        # already lost the time. The length is recoverable from the run
        # itself, so recover it rather than asking twice.
        stored = SqliteRunStore.open(args.out / "run.db").get_meta("days")
        if stored is not None:
            args.days = int(stored)
    spec = epoch_spec(days=args.days)
    compiled = compile_workplace(spec, seed)
    director = epoch_director(seed)
    inner, backend = build_lm(
        args.mode, args.cassette, args.max_calls, args.concurrency
    )
    writer = TelemetryWriter(args.out / "telemetry.jsonl")
    tracker = _DayTracker(
        writer,
        inner if isinstance(inner, BudgetedLM) else None,
        days_already_recorded=_days_recorded(args.out / "telemetry.jsonl"),
    )

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
    grounding = [e for e in notes if "already carries" not in e.payload.note]
    check(
        f"grounding failures {len(grounding)}/{len(acts)} stay under 20% "
        f"({len(braked)} thread-cap brakes counted separately)",
        len(acts) > 0 and len(grounding) <= 0.2 * len(acts),
    )
    plans = Counter(e.payload.day for e in events if e.tag == "sim.agent.plan")
    # Only the records that belong to a day. A rejection routed back to an
    # actor is also a memory and carries no day, so counting them all made
    # the audit report eleven days of reflection in a ten-day world and
    # fail a world that was correct.
    reflections = Counter(
        e.payload.day for e in events if e.tag == "sim.agent.memory" and e.payload.day
    )
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
    # The cap is enforced at grounding time, so replies drafted concurrently
    # before either delivers can overshoot by the in-flight count; delivery
    # quantization co-lands them. Gate on cap + that slack.
    check(
        f"thread cap holds within delivery slack "
        f"(max {max(threads.values(), default=0)}, cap 12 + 2 in-flight)",
        max(threads.values(), default=0) <= 14,
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
    print("# Merrick epoch report\n")
    print(f"Events: {len(events)}")
    for tag, count in tags.most_common():
        print(f"- {tag}: {count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=Path("out/merrick/epoch"))
        p.add_argument("--days", type=int, default=5)
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--mode", choices=("record", "replay"), default="record")
        p.add_argument("--cassette", type=Path, default=DEFAULT_CASSETTE)
        p.add_argument("--window", type=int, default=32)
        p.add_argument("--max-calls", type=int, default=2_000_000)
        p.add_argument(
            "--concurrency",
            type=int,
            default=DEFAULT_CONCURRENCY,
            help="in-flight LM calls; lower it if the key rate-limits",
        )
        p.add_argument("--checkpoint-every", type=int, default=100)
        p.add_argument("--max-steps", type=int, default=None)
    for name in ("status", "report"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, default=Path("out/merrick/epoch"))
    p = sub.add_parser("audit")
    p.add_argument("--out", type=Path, default=Path("out/merrick/epoch"))
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

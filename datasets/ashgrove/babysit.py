"""Supervise an epoch run and fail loudly instead of quietly.

Every failure this project has actually produced is a check here, because
each one cost a run and none of them announced themselves:

* the process dies                  -> report the traceback, stop
* the process hangs                 -> no new events for a while, kill it
* the outside world is mute         -> cues fire but no client mail lands
* nobody logs time                  -> the timesheet cohort produces nothing
* rejections run away               -> the world is fighting the personas
* the provider stalls               -> events stop while the process lives

A run that trips a check is killed and reported rather than left to burn
an hour producing a dataset that validates and is useless. Checks that
need the world to warm up only arm after their grace period.

    uv run python datasets/ashgrove/babysit.py --out out/ashgrove/epoch \
        --pid 12345 [--poll 60]
"""

import argparse
import os
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Health:
    events: int = 0
    emails: int = 0
    time_entries: int = 0
    cues: int = 0
    notes: int = 0
    days: int = 0
    last_change: float = field(default_factory=time.monotonic)


def _counts(db: Path) -> dict[str, int]:
    if not db.exists():
        return {}
    try:
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {}
    try:
        rows = connection.execute("SELECT tag, COUNT(*) FROM events GROUP BY tag")
        return dict(rows)
    except sqlite3.OperationalError:
        # Mid-write is normal; treat as "no reading this poll".
        return {}
    finally:
        connection.close()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _stop(pid: int, reason: str) -> None:
    print(f"\nSTOPPING RUN: {reason}", flush=True)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def supervise(
    out: Path,
    pid: int,
    log_path: Path | None,
    poll: int,
    stall_minutes: int,
    mute_minutes: int,
    max_reject_ratio: float,
) -> int:
    db = out / "run.db"
    health = Health()
    started = time.monotonic()

    while True:
        if not _alive(pid):
            log = log_path or (out.parent / "run.log")
            tail = ""
            if log.exists():
                tail = "\n".join(log.read_text().splitlines()[-12:])
            # A run that stops at quiescence finished its work too.
            finished = "reason=end_time" in tail or "reason=quiescent" in tail
            print("\n=== RUN ENDED ===\n" + tail, flush=True)
            return 0 if finished else 1

        counts = _counts(db)
        if counts:
            total = sum(counts.values())
            if total != health.events:
                health.last_change = time.monotonic()
            health.events = total
            health.emails = counts.get("email.message", 0)
            health.time_entries = counts.get("work.time.logged", 0)
            health.cues = counts.get("sim.cue", 0)
            health.notes = counts.get("sim.gm.note", 0)
            health.days = counts.get("sim.day.started", 0)

        elapsed = (time.monotonic() - started) / 60
        idle = (time.monotonic() - health.last_change) / 60

        print(
            f"[{elapsed:5.1f}m] events {health.events:>6} | days {health.days:>2} | "
            f"mail {health.emails:>4} | time {health.time_entries:>5} | "
            f"cues {health.cues:>4} | rejections {health.notes:>4}",
            flush=True,
        )

        if idle >= stall_minutes and health.events:
            _stop(pid, f"no new events for {idle:.0f} minutes — hung or stalled")
            return 1
        # A world whose outside never speaks validates and is useless: that
        # exact dataset was produced once, 3,980 events with zero mail.
        if elapsed >= mute_minutes and health.cues and health.emails == 0:
            _stop(pid, f"{health.cues} cues fired but no client mail landed")
            return 1
        if elapsed >= mute_minutes and health.days >= 1 and health.time_entries == 0:
            _stop(pid, "a full day passed with no time logged")
            return 1
        acts = max(1, health.emails + health.time_entries)
        if health.notes > 40 and health.notes / acts > max_reject_ratio:
            _stop(
                pid,
                f"{health.notes} rejections against {acts} acts — the world is "
                "fighting the personas",
            )
            return 1

        time.sleep(poll)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--poll", type=int, default=60)
    parser.add_argument("--stall-minutes", type=int, default=12)
    parser.add_argument("--mute-minutes", type=int, default=8)
    parser.add_argument("--max-reject-ratio", type=float, default=0.5)
    args = parser.parse_args(argv)
    return supervise(
        args.out,
        args.pid,
        args.log,
        args.poll,
        args.stall_minutes,
        args.mute_minutes,
        args.max_reject_ratio,
    )


if __name__ == "__main__":
    sys.exit(main())

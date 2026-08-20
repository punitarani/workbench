"""Sweep the window every staged task could use, and print what each one costs.

Filling a `«MEASURE»` by hand means picking a boundary date, guessing what it
implies, and finding out during a rollout. Every staged solver already
computes exactly the two numbers that decide it -- how much the reader must
read, and how many rows come out -- so this drives the real solvers over a
range of windows and prints the table.

    uv run python datasets/merrick/measure_windows.py --state out/merrick/state
    uv run python datasets/merrick/measure_windows.py --state ... \
        --task double-booked-week

**This drives the shipped solver, not a copy of its rule.** A measurement
script that reimplements the admission logic measures the copy, and the two
drift the moment either is touched -- which is the defect that put a
seven-form date table in front of a corpus carrying four.

What it deliberately does NOT do is choose. Reader load and row count trade
against each other, and the choice also depends on how many near-miss
distractors the window contains, which is per-task. It prints the table and
names the window nearest each target; a human still writes the date into the
brief.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"

# What the in-band comparison task settled on: roughly this many items in
# front of the reader. Row count is the second axis -- a register nobody
# would sit down and write is not a better task for being longer.
TARGET_READ = 213
TARGET_ROWS = 30

RETIRED = {"court-clock-computation", "one-sentence-two-dates"}


@dataclass(frozen=True, slots=True)
class Point:
    window_days: int
    read: int
    rows: int
    window_end: str


class NotReady(RuntimeError):
    """The task holds a placeholder this script cannot fill."""


def _load(task: Path):
    """Import a task's solver without running it."""

    path = task / "solution" / "solve.py"
    spec = importlib.util.spec_from_file_location(f"solve_{task.name}", path)
    if spec is None or spec.loader is None:
        raise NotReady(f"{task.name}: no importable solver at {path}")
    module = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = ["solve", "/dev/null"]
    try:
        spec.loader.exec_module(module)
    except Exception as why:
        # A staged task can refuse while it is still being imported, not only
        # when `main` runs: `pending.measure()` is called at module scope, so
        # the placeholder raises during `exec_module`. Catching only
        # SystemExit here let one task abort the whole sweep and take the
        # other four measurable tasks down with it.
        raise NotReady(f"{type(why).__name__}: {why}") from None
    finally:
        sys.argv = saved
    if not hasattr(module, "WINDOW_DAYS"):
        raise NotReady(f"{task.name}: solver declares no WINDOW_DAYS")
    return module


def _run(module, out: Path, window_days: int) -> Point:
    """One window, through the solver's own `main`."""

    module.WINDOW_DAYS = window_days
    # Set the destination on the module, not through argv. Every solver binds
    # `OUT` from `sys.argv` at *import* time, so re-pointing argv here changes
    # nothing -- the first sweep wrote all its output to the placeholder path
    # used during import and this script read a file that was never created.
    # Worse than the crash: had that path ever held a real file, the sweep
    # would have reported a stale register as the measurement.
    module.OUT = out
    saved = sys.argv
    sys.argv = ["solve", str(out)]
    try:
        # A solver still holding another placeholder exits rather than
        # producing a wrong number, which is the behaviour we want; turn it
        # into something this script can report per task.
        with contextlib.redirect_stdout(io.StringIO()):
            module.main()
    except SystemExit as exit_code:
        raise NotReady(str(exit_code) or "solver refused to run") from None
    finally:
        sys.argv = saved

    got = json.loads(out.read_text(encoding="utf-8"))
    # Read the shape rather than a hardcoded key list. Every register in this
    # dataset writes one list of rows, one integer count of what was read, and
    # the window end -- but each names them for its own subject matter, and a
    # hand-kept table of key names fails silently the day a task is added.
    rows = [v for v in got.values() if isinstance(v, list)]
    read = [v for k, v in got.items() if isinstance(v, int) and not isinstance(v, bool)]
    if len(rows) != 1 or len(read) != 1:
        raise NotReady(
            f"expected one row list and one read count, got "
            f"{len(rows)} lists and {len(read)} integers: {sorted(got)}"
        )
    return Point(window_days, read[0], len(rows[0]), str(got.get("window_end", "?")))


def sweep(task: Path, state: Path, scratch: Path, widest: int) -> list[Point]:
    module = _load(task)
    out = scratch / f"{task.name}.json"
    points: list[Point] = []
    for window_days in range(1, widest + 1):
        point = _run(module, out, window_days)
        points.append(point)
        # Past both targets there is nothing left to learn: the register only
        # grows, and a longer window is strictly worse on both axes.
        if point.read > TARGET_READ * 3 and point.rows > TARGET_ROWS * 3:
            break
    return points


def _weekdays_to(state: Path, window_days: int) -> int:
    """Working days inside the window, which is what the brief asks for.

    The brief wants a weekday count and the solver holds a calendar-day
    offset; the two differ by every weekend inside the window, and writing
    one where the other belongs is a mistake this file exists partly to stop
    anyone making by hand.
    """

    import sqlite3

    connection = sqlite3.connect(f"file:{state / 'gmail.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(connection.execute("SELECT key, value FROM meta"))["epoch"]
    )
    return sum(
        1
        for offset in range(window_days)
        if (epoch + datetime.timedelta(days=offset)).weekday() < 5
    )


def _nearest(points: list[Point], key, target: int) -> Point | None:
    return min(points, key=lambda p: abs(key(p) - target)) if points else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--widest", type=int, default=130)
    parser.add_argument(
        "--scratch", type=Path, default=Path("/tmp/merrick-measure-windows")
    )
    args = parser.parse_args()

    if not args.state.is_dir():
        print(f"no served state at {args.state}", file=sys.stderr)
        return 2
    args.scratch.mkdir(parents=True, exist_ok=True)
    os.environ["WORKBENCH_STATE"] = str(args.state)

    wanted = set(args.task)
    tasks = sorted(
        p
        for p in TASKS.iterdir()
        if p.is_dir()
        and not p.name.startswith("_")
        and p.name not in RETIRED
        and (not wanted or p.name in wanted)
    )
    if not tasks:
        print("no staged tasks matched", file=sys.stderr)
        return 2

    for task in tasks:
        print(f"\n=== {task.name}")
        try:
            points = sweep(task, args.state, args.scratch, args.widest)
        except NotReady as why:
            print(f"    not measurable yet: {why}")
            continue
        if not points:
            print("    solver produced no points")
            continue

        print(
            f"    {'cal.days':>8} {'workdays':>8} {'read':>7} {'rows':>6}  window_end"
        )
        step = max(1, len(points) // 12)
        shown = points[::step] + ([points[-1]] if len(points) > 1 else [])
        for point in dict.fromkeys(shown):
            print(
                f"    {point.window_days:8d} "
                f"{_weekdays_to(args.state, point.window_days):8d} "
                f"{point.read:7d} {point.rows:6d}  {point.window_end}"
            )

        by_read = _nearest(points, lambda p: p.read, TARGET_READ)
        by_rows = _nearest(points, lambda p: p.rows, TARGET_ROWS)
        for label, point in (
            (f"closest to {TARGET_READ} read", by_read),
            (f"closest to {TARGET_ROWS} rows", by_rows),
        ):
            if point is None:
                continue
            print(
                f"    {label:>24}: {point.window_days} calendar days = "
                f"{_weekdays_to(args.state, point.window_days)} working days, "
                f"ending {point.window_end} "
                f"({point.read} read, {point.rows} rows)"
            )
        if by_read and by_rows and by_read.window_days != by_rows.window_days:
            print(
                "    the two targets disagree; reader load and register length "
                "trade off here, so pick by which one the task is about."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

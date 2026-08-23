"""Fill or unfill `live-commitment-register` for a probe, reversibly.

    uv run python datasets/merrick/fill_commitment_task.py \
        fill --first-day 49 --last-day 74
    uv run python datasets/merrick/fill_commitment_task.py unfill

Filling a task to probe it and unfilling it afterwards is not the same as
editing it twice, and doing it by hand went wrong on both attempts. The
mechanism is mechanical:

* filling makes `measure` unused, `ruff --fix` removes the import, and the
  unfill then restores `measure()` calls the file can no longer resolve —
  so the task silently stops being able to refuse an unmeasured run;
* the literals go in behind a comment saying `PROBE ONLY — not committed`,
  and both times they were committed anyway, window and all.

So the round trip is a command, and `--check` proves it: fill, unfill, and
compare against `git show HEAD` byte for byte.

What this does NOT do is choose the values. `measure_commitment_window.py`
does that, and refuses a window that cannot carry the task. This only moves
them in and out.

**`unfill` is `git checkout`, so it discards everything uncommitted in the
task — including a real fix made while the task was filled.** That is the
trade for a round trip that provably lands on HEAD, and it is a live hazard:
most of the defects in this task were found *during* a probe, with the fill
in place. Commit the structural change first, then unfill. If you forget,
the change is gone and the probe that motivated it is the only record it
ever existed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent / "tasks" / "live-commitment-register"
SOLVER = TASK / "solution" / "solve.py"
VERIFIER = TASK / "checks" / "verify.py"
BRIEF = TASK / "instruction.md"

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_EODS = ("EOD", "COB", "end of day", "end of the day", "close of business")


def _admitted() -> list[tuple[str, str]]:
    """Every compound in both directions ahead of either part."""

    forms: list[tuple[str, str]] = []
    forms += [(f"{e} tomorrow", "tomorrow") for e in _EODS]
    forms += [(f"tomorrow {e}", "tomorrow") for e in _EODS]
    for day in _WEEKDAYS:
        forms += [(f"{day} {e}", day.lower()) for e in _EODS]
    for day in _WEEKDAYS:
        forms += [(f"{e} {day}", day.lower()) for e in _EODS]
    forms += [(e, "eod") for e in _EODS]
    forms += [
        ("EOW", "end of week"),
        ("end of the week", "end of week"),
        ("end of week", "end of week"),
        ("tomorrow", "tomorrow"),
    ]
    return forms + [(day, day.lower()) for day in _WEEKDAYS]


_UNFILLED = {
    SOLVER: [
        (
            r"    WINDOW_FIRST_DAY = \d+\n    WINDOW_LAST_DAY = \d+",
            '    WINDOW_FIRST_DAY = measure(\n        "zero-based day index of the '
            "window's first day\"\n    )\n    WINDOW_LAST_DAY = measure(\n        "
            '"zero-based day index of the window\'s last day"\n    )',
        )
    ],
    VERIFIER: [
        (
            r'WINDOW_FIRST_DATE = "[\d-]+"',
            "WINDOW_FIRST_DATE = measure(\n    \"the window's first day as an ISO "
            'calendar date"\n)',
        ),
        (
            r'WINDOW_LAST_DATE = "[\d-]+"',
            "WINDOW_LAST_DATE = measure(\n    \"the window's last day as an ISO "
            'calendar date"\n)',
        ),
        (
            r"OWNER_FORMS = \[[^\]]*\]",
            'OWNER_FORMS = measure("the brief\'s owner-phrase list, as a closed set")',
        ),
    ],
}


def _ruff(paths: list[Path]) -> None:
    for argv in (["check", "--fix", "-q"], ["format", "-q"]):
        subprocess.run(
            [sys.executable, "-m", "ruff", *argv, *[str(p) for p in paths]],
            check=False,
            capture_output=True,
        )


def _ensure_import(path: Path, after: str) -> None:
    """Put `measure` back. `ruff --fix` removes it while the task is filled,
    and without it the unfilled file raises NameError instead of the
    `Unmeasured` refusal that is the whole point of the placeholder."""

    body = path.read_text()
    if "from pending import measure" in body:
        return
    assert body.count(after) == 1, path
    path.write_text(
        body.replace(after, after + "from pending import measure  # noqa: E402\n")
    )


def unfill() -> None:
    subprocess.run(["git", "checkout", "--", str(TASK)], check=True)
    print("unfilled: task restored to HEAD")


def fill(first: int, last: int, epoch: dt.date) -> None:
    body = SOLVER.read_text()
    body = re.sub(
        r"    WINDOW_FIRST_DAY = measure\(.*?\)\n    WINDOW_LAST_DAY = measure\(.*?\)",
        f"    WINDOW_FIRST_DAY = {first}\n    WINDOW_LAST_DAY = {last}",
        body,
        flags=re.S,
    )
    SOLVER.write_text(body)

    opens, closes = epoch + dt.timedelta(days=first), epoch + dt.timedelta(days=last)
    body = VERIFIER.read_text()
    body = re.sub(
        r"WINDOW_FIRST_DATE = measure\(.*?\)",
        f'WINDOW_FIRST_DATE = "{opens.isoformat()}"',
        body,
        flags=re.S,
    )
    body = re.sub(
        r"WINDOW_LAST_DATE = measure\(.*?\)",
        f'WINDOW_LAST_DATE = "{closes.isoformat()}"',
        body,
        flags=re.S,
    )
    body = re.sub(
        r"OWNER_FORMS = measure\(.*?\)",
        "OWNER_FORMS = [\"I'll\", 'I will']",
        body,
        flags=re.S,
    )
    body = re.sub(
        r"ADMITTED = measure\(.*?\n\)", f"ADMITTED = {_admitted()!r}", body, flags=re.S
    )
    VERIFIER.write_text(body)
    _ruff([SOLVER, VERIFIER])
    print(
        f"filled: days {first}-{last} ({opens:%A %-d %B %Y} to {closes:%A %-d %B %Y})"
    )
    print("  the brief's own values and the PINNED digests are not touched here —")
    print(
        "  fill them from measure_commitment_window.py, then unfill before committing"
    )


def check() -> int:
    before = subprocess.run(
        ["git", "status", "--porcelain", str(TASK)], capture_output=True, text=True
    ).stdout
    if before.strip():
        print("refusing --check: the task already has uncommitted changes")
        return 1
    fill(49, 74, dt.date(2026, 1, 5))
    _ensure_import(
        SOLVER, "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))\n"
    )
    unfill()
    after = subprocess.run(
        ["git", "status", "--porcelain", str(TASK)], capture_output=True, text=True
    ).stdout
    if after.strip():
        print("ROUND TRIP DIRTY:\n" + after)
        return 1
    print("round trip clean: fill then unfill leaves the task identical to HEAD")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fill", "unfill", "check"))
    parser.add_argument("--first-day", type=int)
    parser.add_argument("--last-day", type=int)
    parser.add_argument("--epoch", default="2026-01-05")
    args = parser.parse_args(argv)
    if args.action == "unfill":
        unfill()
        return 0
    if args.action == "check":
        return check()
    if args.first_day is None or args.last_day is None:
        raise SystemExit("fill needs --first-day and --last-day")
    fill(args.first_day, args.last_day, dt.date.fromisoformat(args.epoch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

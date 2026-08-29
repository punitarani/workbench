"""Cut an existing task to a shorter window, as a task of its own.

    uv run python scripts/window_variant.py --dataset merrick \
        --task commitment-revision-register --last-day 90 --name short

A window is the strongest difficulty dial this tree has measured, and it is
the only one that changes the task without changing what is being asked.
Measured on one register: at 42 days the median person revises ONCE and the
strongest tier scores 1.000; at 147 days the median is 3.5 and the same
tier scores 0.795. Same rule, same key, same grader.

So a shorter window is a different measurement rather than a copy, in the
way that a shorter exam is a different exam. This makes one, consistently,
instead of by hand -- because doing it by hand is how a brief comes to
state one window while its solver reads another, and nothing errors when
that happens.

**What it changes, and nothing else:**

  * the solver's `WINDOW_LAST_DAY` and the verifier's, if it names one;
  * the four generated literals in the brief -- the two boundary dates, the
    working-day count and the meeting count -- recomputed from the world
    rather than edited;
  * the deliverable's filename, the task's name and its `primary_field`,
    because two tasks writing the same file cannot both be graded.

**What it does NOT do** is decide whether the result is worth shipping.
Cutting a window shortens the chains, and past some point there is no chain
left to reconstruct: the register collapses toward one row per person and
the task measures extraction alone. Build it, measure the depth, and read
the floors before believing it.
"""

import argparse
import collections
import datetime as dt
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]


def _world(dataset: str) -> Path:
    return REPO / "out" / dataset / "bundle" / "state"


def _facts(state: Path, first_day: int, last_day: int) -> dict:
    """The window's own figures, read from the world rather than typed.

    `first_day` matters and was omitted at first. A solver here may open its
    window on day 1 rather than day 0 -- the epoch's first day is a Monday
    and the register starts on the Tuesday -- so computing the brief's dates
    from day 0 states a window one day wider than the solver reads. The
    second derivation caught it: it windows by the brief's CALENDAR DATES
    where the solver windows by offsets, which is exactly the disagreement
    that pair exists to produce.
    """

    connection = sqlite3.connect(f"file:{state / 'meetings.db'}?mode=ro", uri=True)
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    epoch = dt.datetime.fromisoformat(meta["epoch"])
    zone = ZoneInfo(meta.get("timezone", "America/New_York"))
    low = first_day * 86_400
    high = (last_day + 1) * 86_400 - 1
    rooms = [
        (started, title)
        for _mid, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    ]
    connection.close()
    if not rooms:
        raise SystemExit(f"no meetings at or before day {last_day}")
    days = sorted({(epoch + dt.timedelta(seconds=s)).astimezone(zone).date() for s, _t in rooms})
    return {
        "first": days[0],
        "last": days[-1],
        "working_days": len(days),
        "meetings": len(rooms),
    }


def _stamp(date: dt.date) -> str:
    return f"{date:%A} {date.day} {date:%B %Y}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--last-day", type=int, required=True)
    parser.add_argument("--name", required=True, help="suffix for the new task")
    args = parser.parse_args(argv)

    tasks = REPO / "datasets" / args.dataset / "tasks"
    source = tasks / args.task
    target = tasks / f"{args.task}-{args.name}"
    if not source.is_dir():
        raise SystemExit(f"no such task: {source}")
    if target.exists():
        shutil.rmtree(target)

    for part in (".gitignore", "instruction.md", "task.toml"):
        (target).mkdir(parents=True, exist_ok=True)
        if (source / part).is_file():
            shutil.copy(source / part, target / part)
    for part in ("solution/solve.py", "checks/verify.py", "tests/criteria.py"):
        (target / part).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source / part, target / part)

    solver = target / "solution" / "solve.py"
    text = solver.read_text()
    opens = re.search(r"^\s*WINDOW_FIRST_DAY\s*=\s*(\d+)", text, re.M)
    facts = _facts(
        _world(args.dataset), int(opens.group(1)) if opens else 0, args.last_day
    )
    # Anchored to the assignment, on its own line.
    #
    # `WINDOW_LAST_DAY[^=]*=` looks tighter than it is: `[^=]` matches
    # NEWLINES, so the match began at the word WINDOW_LAST_DAY inside a
    # COMMENT four lines above and ran forward to the next `=` in the file
    # -- which belonged to WINDOW_FIRST_DAY. The first day was set to the
    # last day, the window became one day wide, and the oracle came out
    # empty. The empty-oracle gate caught it; nothing else would have.
    text, changed = re.subn(
        r"^(\s*WINDOW_LAST_DAY\s*=\s*)\d+",
        rf"\g<1>{args.last_day}",
        text,
        flags=re.M,
    )
    if not changed:
        raise SystemExit("the solver states no WINDOW_LAST_DAY to move")
    solver.write_text(text)

    # The verifier states its window in whichever unit it chose, and the
    # choice is deliberate: one derivation reads day OFFSETS and the other
    # CALENDAR DATES, so a boundary wrong in one shows up as a disagreement
    # instead of being shared. Both forms have to be moved, and moving only
    # the one this script happened to know about left a verifier reading the
    # whole six months against a solver reading three.
    checker = target / "checks" / "verify.py"
    text = checker.read_text()
    text, by_offset = re.subn(
        r"^(\s*_WINDOW_LAST_DAY\s*=\s*)\d+",
        rf"\g<1>{args.last_day}",
        text,
        flags=re.M,
    )
    text, by_date = re.subn(
        r'^(WINDOW_LAST_DATE\s*=\s*")\d{4}-\d{2}-\d{2}(")',
        rf'\g<1>{facts["last"].isoformat()}\g<2>',
        text,
        flags=re.M,
    )
    text = re.sub(
        r'^(WINDOW_FIRST_DATE\s*=\s*")\d{4}-\d{2}-\d{2}(")',
        rf'\g<1>{facts["first"].isoformat()}\g<2>',
        text,
        flags=re.M,
    )
    if not (by_offset or by_date):
        raise SystemExit(
            "the verifier states its window in neither form this knows "
            "(_WINDOW_LAST_DAY or WINDOW_LAST_DATE); teach it the third "
            "rather than shipping a variant whose two derivations read "
            "different windows"
        )
    checker.write_text(text)

    # The brief's four generated literals, recomputed rather than edited.
    # They are written in quadruple asterisks precisely because they are
    # generated, which is also what makes a stale one invisible.
    brief = target / "instruction.md"
    text = brief.read_text()
    literals = re.findall(r"\*{4}([^*]+)\*{4}", text)
    if len(literals) < 4:
        raise SystemExit(f"expected 4 generated literals in the brief, found {len(literals)}")
    replacements = [
        _stamp(facts["first"]),
        _stamp(facts["last"]),
        str(facts["working_days"]),
        str(facts["meetings"]),
    ]
    for old, new in zip(literals[:4], replacements):
        text = text.replace(f"****{old}****", f"****{new}****", 1)
    deliverable = re.search(r'DELIVERABLE = "([^"]+)"', (target / "tests" / "criteria.py").read_text())
    if deliverable is None:
        raise SystemExit("the criteria name no DELIVERABLE")
    stem, _dot, ext = deliverable.group(1).rpartition(".")
    renamed = f"{stem}_{args.name}.{ext}"
    text = text.replace(deliverable.group(1), renamed)
    brief.write_text(text)

    for part, pattern in (
        ("tests/criteria.py", None),
        ("solution/solve.py", None),
        ("checks/verify.py", None),
    ):
        p = target / part
        p.write_text(p.read_text().replace(deliverable.group(1), renamed))

    manifest = target / "task.toml"
    text = manifest.read_text()
    text = text.replace(f'workbench/{args.dataset}-{args.task}"',
                        f'workbench/{args.dataset}-{args.task}-{args.name}"')
    text = text.replace(deliverable.group(1), renamed)
    manifest.write_text(text)

    # Re-pin the brief's digests, but only after proving the section
    # changed by the RENAME and by nothing else.
    #
    # The pin exists so a reworded brief cannot silently drift from the
    # verifier that implements it, and a variant that renames a deliverable
    # trips it legitimately. Pasting the new digest in to make the check
    # pass is what the pin's own message warns against, so this reconstructs
    # the old section from the new one by undoing the rename and refuses if
    # the two do not match.
    sys.path.insert(0, str(REPO / "datasets" / args.dataset))
    from brief_pins import digest  # noqa: E402

    original = (source / "instruction.md").read_text()
    updated = brief.read_text()
    checker_text = checker.read_text()
    for heading in re.findall(r'"(## [^"]+)": "[0-9a-f]{16}"', checker_text):
        def section(text: str) -> str:
            start = text.index(heading)
            end = text.find("\n## ", start + 1)
            return text[start : end if end > 0 else len(text)]

        was, now = section(original), section(updated)
        if now.replace(renamed, deliverable.group(1)) != was:
            raise SystemExit(
                f"{heading} differs from the source by more than the "
                "deliverable's name; re-pin it by hand after reading it"
            )
        checker_text = re.sub(
            rf'("{re.escape(heading)}": ")[0-9a-f]{{16}}(")',
            rf"\g<1>{digest(updated, heading)}\g<2>",
            checker_text,
        )
    checker.write_text(checker_text)

    print(f"  {target.relative_to(REPO)}")
    print(f"    window: day 0..{args.last_day}  ->  {facts['first']} .. {facts['last']}")
    print(f"    {facts['working_days']} working days, {facts['meetings']} meetings")
    print(f"    deliverable: {renamed}")
    print("    now build it, and READ the chain depth and the floors before shipping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

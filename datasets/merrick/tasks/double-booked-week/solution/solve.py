"""RETIRED. Do not build this task; it grades a seeding artifact.

Kept as a worked example of a measurement that was correct and useless.

The justification was 54 genuine diary clashes against 240 pairs that
merely touch -- a 4.4:1 trap ratio, and a loose reader scoring 16%
precision. Every one of those numbers is right. Grouped by date, **47 of
the 54 fall on the first recorded day**. Outside that pile-up the firm
produced one clash in seventeen working days.

The first reading of that was a seeding burst -- a world that schedules
many events at the epoch and few afterwards. It is not. **Zero events are
genuinely scheduled on day zero.** Forty-five of them have a wall-clock
time of day in a field that holds seconds-from-epoch (`31500` = 08:45), so
they all collapse onto the epoch's own date, and collapsing onto one day
makes each of them overlap every other. 96% of every conflict in the world
involves one of those events.

So this task was never measuring a scheduling pattern. It was measuring a
unit bug, faithfully, in a register that would have graded models on it.

An independent audit reached the same verdict from three directions and
added two more: the register's `date` column is constant within any usable
window, which hands over a quarter of the per-row score for free; and the
task had already met the retirement condition written into this very
docstring -- "retire it rather than prop it up if adjacency ever stops
outnumbering overlap".

The replacement is `unanswered-question-register`, which was measured by
date *before* it was written. That check found the mirror-image artifact
at the other end of the record and turned it into a rule, rather than
discovering it after the task was built.

The lesson, which is now in the `validating-task-premises` skill: a rate
computed over a window can be dominated by what happens at one edge of it,
and a total will never show you. It is one line to check.
"""

import datetime
import itertools
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("double_bookings.json")

# «MEASURE: working days in the window. At the recorded rate -- ~47 events
# and ~3.4 genuine clashes per working day -- two weeks puts ~470 events in
# front of the reader for ~34 rows. Re-measure on the finished record.»
WINDOW_DAYS: int | None = None


def overlap_minutes(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Whole minutes two intervals share; 0 when they merely touch.

    Half-open on purpose: `min(end) - max(start)` is positive only when the
    intervals genuinely intersect, and is exactly 0 for the back-to-back
    case the brief excludes. Writing this as `a_start <= b_end` instead --
    the closed-interval form that reads more naturally -- admits all 240
    touching pairs.
    """

    return max(0, (min(a_end, b_end) - max(a_start, b_start)) // 60)


def main() -> None:
    if WINDOW_DAYS is None:
        raise SystemExit(
            "double-booked-week: WINDOW_DAYS is still a placeholder. Measure "
            "the finished record before building this task."
        )

    calendar = sqlite3.connect(f"file:{STATE / 'calendar.db'}?mode=ro", uri=True)

    # Seconds from the world's epoch, not a date string. Comparing a served
    # `time` against an ISO date compiles, runs, and windows on a
    # lexicographic accident.
    cutoff = WINDOW_DAYS * 86_400
    epoch = datetime.datetime.fromisoformat(
        dict(calendar.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(calendar.execute("SELECT person_id, name FROM people"))

    events: dict[str, tuple[int, int, str]] = {}
    for event_id, summary, start, end in calendar.execute(
        "SELECT calendar_event_id, summary, start_time, end_time FROM calendar_events"
    ):
        if start >= cutoff:
            continue
        events[event_id] = (start, end, summary)

    diary: dict[str, list[str]] = {}
    for event_id, person_id in calendar.execute(
        "SELECT calendar_event_id, person_id FROM attendees"
    ):
        if event_id in events:
            diary.setdefault(person_id, []).append(event_id)

    rows = []
    for person_id, event_ids in diary.items():
        # Sort by start, then by id, so the pair below is already in the
        # order the brief fixes and the tie-break needs no second thought.
        ordered = sorted(event_ids, key=lambda e: (events[e][0], e))
        for first, second in itertools.combinations(ordered, 2):
            a_start, a_end, a_title = events[first]
            b_start, b_end, b_title = events[second]
            shared = overlap_minutes(a_start, a_end, b_start, b_end)
            if not shared:
                continue
            rows.append(
                {
                    "person": people.get(person_id, person_id),
                    "first_event": first,
                    "second_event": second,
                    "first_title": a_title,
                    "second_title": b_title,
                    "date": (epoch + datetime.timedelta(seconds=a_start))
                    .date()
                    .isoformat(),
                    "overlap_minutes": shared,
                }
            )

    rows.sort(key=lambda r: (r["person"], r["first_event"], r["second_event"]))
    OUT.write_text(
        json.dumps(
            {
                "window_end": (epoch + datetime.timedelta(seconds=cutoff - 1))
                .date()
                .isoformat(),
                "events_read": len(events),
                "double_bookings": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

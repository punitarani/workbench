"""Reference solver: genuine diary clashes, not back-to-back meetings.

STAGED. `WINDOW_DAYS` is not chosen; `main()` refuses while it is None.
Fill it from a measurement of the finished record, never from intuition.

**The difficulty is one boundary, and it was measured before the task was
written.** Over sixteen recorded working days this world produces 54 pairs
that genuinely overlap and **240 pairs that touch exactly** -- one ends at
the moment the next begins. A reader who treats touching as clashing
reports 294 rows where 54 are right, and precision falls to 18%. Four
traps for every signal is the whole task; everything else here is
bookkeeping.

That ratio is not an accident of this world and would not survive a
different one. It comes from scheduling on a fixed grid, which is what
makes adjacency the common case and simultaneity the exception. Re-measure
it before trusting the band: if back-to-back pairs ever stop outnumbering
overlaps, this task has lost its difficulty and should be retired rather
than propped up.

**Ordering the pair is not cosmetic.** On a fixed grid many events start at
the same moment, so "earlier first" leaves ties, and an unordered pair keys
two ways -- the same clash then reads as one miss and one invention, and
row F1 scores it twice. The brief fixes the tie-break to the smaller id as
text and this follows it.

One trap that is *not* here, deliberately: declined invitations. The record
holds 147 accepts against 4 declines, so a rule turning on declines would
be starved, and a starved clause reads as difficulty while grading noise.
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

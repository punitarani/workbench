"""Second derivation of the double-booking register.

An independent verifier exists so the answer key is derived twice. Copying
the solver's arithmetic reproduces the solver's bugs and then certifies the
two agree -- a check that cannot fail.

**The arithmetic here is deliberately a different shape.** `solve.py`
computes `min(end) - max(start)`, which is where a boundary bug would live:
one comparison written `<=` instead of `<` turns all 240 back-to-back pairs
into clashes. This file uses inclusion-exclusion instead -- the two
durations less the span they jointly cover -- which needs no comparison at
all and is positive exactly when they truly intersect.

The first version of this file intersected **sets of clock-minutes**, and
it disagreed with the solver on one row in forty-seven: 26 minutes against
25. Neither was wrong. Three events in this diary do not begin on a whole
minute, and "how many whole minutes do they share" has two honest readings
for those -- shared duration floored, or clock-minutes jointly occupied.
The brief was ambiguous, so an agent could have been marked wrong for a
defensible reading. That is a defect in the task, not in either
implementation, and it was found only because the two derivations were
genuinely independent. The brief now fixes the reading; this file follows
the brief.

`insists` pins the assumptions to the brief, because zero shared code is
not enough on its own: two files can hardcode the same reading of a spec
and never disagree. Flipping the boundary rule in the brief must fail here.
"""

import json
import sqlite3
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
BRIEF = (TASK / "instruction.md").read_text(encoding="utf-8")


class BriefChanged(AssertionError):
    """The brief no longer says what this file's arithmetic assumes."""


def insists(condition: object, what: str) -> None:
    if not condition:
        raise BriefChanged(
            f"instruction.md no longer states: {what}. The verifier's "
            "arithmetic assumes it. Re-read the brief and this file together "
            "-- do not relax the assertion."
        )


_FOLDED = " ".join(BRIEF.split())

# The boundary. This is the whole task, so it is pinned by the brief's own
# worked example rather than by a paraphrase that could drift.
insists(
    "share at least one minute" in _FOLDED,
    "a clash requires the two events to share at least one minute",
)
insists(
    "10:00–10:30 and an event running 10:30–11:00 share no minute" in _FOLDED,
    "the worked example saying touching events do NOT clash",
)
insists(
    "10:29" in _FOLDED,
    "the worked example saying a one-minute overlap DOES clash",
)
# The pair order, without which the same clash keys two ways.
insists(
    "is the one that starts earlier" in _FOLDED,
    "first_event is the earlier-starting event",
)
insists(
    "sorts first as text" in _FOLDED,
    "ties on start time break on the id sorting first as text",
)
insists(
    "organising counts as attending" in _FOLDED,
    "the organizer counts as an attendee",
)
insists("not by UTC" in _FOLDED, "dates are read in the firm's time zone")
insists(
    "shared time in whole minutes, rounded down" in _FOLDED.replace("**", ""),
    "overlap_minutes is shared seconds divided by 60 and floored -- NOT the "
    "count of clock-minutes both events occupy, which differs for the three "
    "events in this diary that do not start on a whole minute",
)
insists(
    "less than one whole minute do not clash" in _FOLDED.replace("**", ""),
    "the clash test uses the same floored definition",
)
insists(
    "make two rows" in _FOLDED.replace("**", ""),
    "two people caught by one pair of events make two rows",
)


def shared_minutes(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Whole minutes of shared time, by inclusion-exclusion.

    Two intervals covering `da` and `db` seconds and jointly spanning
    `span` seconds share `da + db - span` -- negative when they are
    disjoint, exactly zero when they touch. No `<` to write the wrong way
    round, and no minute-set representation to smuggle in a second reading
    of the brief.
    """

    span = max(a_end, b_end) - min(a_start, b_start)
    return max(0, (a_end - a_start) + (b_end - b_start) - span) // 60


def recompute(state: Path, window_days: int) -> dict:
    import datetime

    calendar = sqlite3.connect(f"file:{state / 'calendar.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(calendar.execute("SELECT key, value FROM meta"))["epoch"]
    )
    limit = window_days * 86_400
    named = dict(calendar.execute("SELECT person_id, name FROM people"))

    held = {}
    for ident, title, begins, finishes in calendar.execute(
        "SELECT calendar_event_id, summary, start_time, end_time FROM calendar_events"
    ):
        if begins < limit:
            held[ident] = (begins, finishes, title)

    seats = {}
    for ident, person in calendar.execute(
        "SELECT calendar_event_id, person_id FROM attendees"
    ):
        if ident in held:
            seats.setdefault(person, set()).add(ident)

    out = []
    for person, idents in seats.items():
        listed = sorted(idents)
        for i, one in enumerate(listed):
            for other in listed[i + 1 :]:
                shared = shared_minutes(
                    held[one][0], held[one][1], held[other][0], held[other][1]
                )
                if shared == 0:
                    continue
                # Earlier start wins; the smaller id as text breaks a tie.
                pair = sorted((one, other), key=lambda e: (held[e][0], e))
                first, second = pair
                out.append(
                    {
                        "person": named.get(person, person),
                        "first_event": first,
                        "second_event": second,
                        "first_title": held[first][2],
                        "second_title": held[second][2],
                        "date": (epoch + datetime.timedelta(seconds=held[first][0]))
                        .date()
                        .isoformat(),
                        "overlap_minutes": shared,
                    }
                )
    out.sort(key=lambda r: (r["person"], r["first_event"], r["second_event"]))
    return {"events_read": len(held), "double_bookings": out}


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: verify.py <state-dir> <window-days> <oracle.json>")
        return 2
    mine = recompute(Path(sys.argv[1]), int(sys.argv[2]))
    theirs = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    ok = True
    if mine["events_read"] != theirs.get("events_read"):
        print(f"events_read: {mine['events_read']} vs {theirs.get('events_read')}")
        ok = False
    key = lambda r: (r["person"], r["first_event"], r["second_event"])  # noqa: E731
    left = {key(r): r for r in mine["double_bookings"]}
    right = {key(r): r for r in theirs.get("double_bookings", [])}
    for k in sorted(set(left) | set(right)):
        if k not in right:
            print(f"only the verifier finds {k}")
            ok = False
        elif k not in left:
            print(f"only the solver finds {k}")
            ok = False
        elif left[k] != right[k]:
            print(f"{k} differs: {left[k]} vs {right[k]}")
            ok = False
    print(
        f"{'agree' if ok else 'DISAGREE'}: "
        f"{len(left)} verifier rows, {len(right)} solver rows"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

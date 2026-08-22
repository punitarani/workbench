"""What the meeting-transcript corpus can and cannot support a task on.

    uv run python datasets/merrick/measure_transcripts.py [--days N]

Transcripts are the newest surface in this world and the only one a
pull-and-aggregate script cannot flatten. Every other corpus has an id to
group by and a column to sum: `list_activities` hands back 21,597 rows in
about seventy seconds at zero context cost, and the arithmetic over them
is three lines. A transcript has neither. A commitment made out loud is
not a field, so finding one means reading.

That makes it the most promising corpus in the world for a task, and the
easiest to write a false brief about, because nothing in it is countable
until somebody counts it. This screen counts it.

Three things decide whether a transcript task is possible at all, and each
has already been got wrong somewhere in this dataset:

**Is the window readable?** A brief that needs 200,000 words read is
measuring stamina and budget, not comprehension. The screen prints words
and meetings per window so the choice is made on a number.

**Does the material actually occur?** A rule about commitments is worth
nothing if the firm's meetings are status updates with no commitments in
them. `end of month` matched zero of 2,717 mail messages in the task that
taught this dataset to measure first.

**Is the material spread, or concentrated?** A daily docket call that is
180 of the 723 meetings can carry the whole corpus statistic while every
other room is silent, and a task windowed off the docket call then finds
nothing. Concentration is printed per meeting title.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sqlite3
import statistics
from pathlib import Path

STATE = Path(os.environ.get("WORKBENCH_STATE", "out/merrick/bundle/state"))

# What a professional says when they take on work, set a date, or change
# one. Deliberately phrase-level rather than single words: "I'll" is a
# commitment and "will" alone is a weather forecast.
#
# These are SCREENS FOR MEASUREMENT, not a task's admitted forms. A brief
# that graded these exact patterns would be a literal-matching rule, which
# is measured dead on this world twice over (Opus 5 at 1.000 and 0.976).
# What they are for is answering whether the material is there at all.
SHAPES: dict[str, str] = {
    "commitment": r"\bI(?:'ll| will| can| am going to)\b",
    "owner named": r"\b(?:owns?|owner on|will take|taking|will handle|handling)\b",
    "weekday deadline": (
        r"\b(?:by|before|on|this|next)\s+"
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday)\b"
    ),
    "dated deadline": (
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2}\b"
    ),
    "relative deadline": r"\b(?:end of (?:the )?(?:day|week)|EOD|COB|tomorrow)\b",
    "revision": (
        r"\b(?:actually|instead|moved to|slipped|pushed|changed to|no longer|"
        r"revised|scratch that)\b"
    ),
    "pushback": (
        r"\b(?:is tight|can't|cannot|won't work|not going to|concerned|"
        r"disagree|too tight)\b"
    ),
    "hand-off": r"\b(?:hand(?:ing)? (?:it |this )?(?:off|over)|pass(?:ing)? to)\b",
}

# Below this a window is not a task, it is a coin flip; above the word
# ceiling it is a reading-stamina test. Both numbers come from this
# dataset's own history: three tasks were retired for producing 0-3 rows,
# and the in-band precedent settled on a ~213-message window.
MEETING_FLOOR = 25
WORD_CEILING = 60_000


def _rows(day_limit: int | None) -> tuple[list, dict]:
    path = STATE / "meetings.db"
    if not path.is_file():
        raise SystemExit(
            f"no meetings.db under {STATE}. Build the bundle first — and if "
            "the bundle predates the meetings system, rebuild it, because a "
            "world recorded with transcripts and projected without them "
            "serves none."
        )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    horizon = None if day_limit is None else day_limit * 86_400
    meetings = {
        row[0]: row[1:]
        for row in connection.execute(
            "SELECT meeting_id, title, started, turn_count, word_count FROM meetings"
        )
        if horizon is None or row[2] < horizon
    }
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in meetings
    ]
    connection.close()
    return turns, meetings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=None, help="first N days only")
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args(argv)

    turns, meetings = _rows(args.days)
    if not meetings:
        raise SystemExit("no meetings in that window")

    words = sum(m[3] for m in meetings.values())
    per_meeting = [m[2] for m in meetings.values()]
    per_turn = [len((t[3] or "").split()) for t in turns]
    scope = f"first {args.days} days" if args.days else "whole record"

    print(
        f"corpus: {len(meetings)} meetings, {len(turns)} turns, "
        f"{words:,} words ({scope})"
    )
    print(
        f"  turns per meeting: median {statistics.median(per_meeting):.0f}, "
        f"max {max(per_meeting)}"
    )
    print(
        f"  words per turn:    median {statistics.median(per_turn):.0f}, "
        f"max {max(per_turn)}"
    )

    verdicts = []
    if len(meetings) < MEETING_FLOOR:
        verdicts.append(
            f"only {len(meetings)} meetings, under the {MEETING_FLOOR} floor"
        )
    if words > WORD_CEILING:
        verdicts.append(
            f"{words:,} words to read, over the {WORD_CEILING:,} ceiling — that "
            "is stamina and budget, not comprehension"
        )
    print("  VERDICT: " + ("; ".join(verdicts) if verdicts else "usable"))

    print("\nwhat the rooms actually contain")
    for label, pattern in SHAPES.items():
        rx = re.compile(pattern, re.I)
        hits = [t for t in turns if rx.search(t[3] or "")]
        rooms = {t[0] for t in hits}
        dead = "" if hits else "   <-- ABSENT: a brief about this would grade nothing"
        print(
            f"  {label:18s} {len(hits):5d} turns in {len(rooms):4d} meetings "
            f"({len(rooms) / len(meetings):5.0%}){dead}"
        )

    # Concentration. A statistic carried by one recurring meeting is not a
    # property of the firm, and a task windowed away from that meeting
    # finds nothing.
    print("\nconcentration — is the material spread, or is it one room?")
    by_title = collections.Counter(m[0] for m in meetings.values())
    commit = re.compile(SHAPES["commitment"], re.I)
    carrying = collections.Counter(
        meetings[t[0]][0] for t in turns if commit.search(t[3] or "")
    )
    for title, count in by_title.most_common(args.top):
        share = carrying[title] / max(sum(carrying.values()), 1)
        print(
            f"  {title[:42]:44s} {count:4d} meetings, {carrying[title]:4d} "
            f"commitment turns ({share:5.1%} of all)"
        )

    # Who speaks. A corpus where one person says everything grades one
    # person's prose, and `distinct_speakers` becomes a constant.
    speakers = collections.Counter(t[2] for t in turns)
    print(f"\nspeakers: {len(speakers)} distinct")
    busiest = speakers.most_common(1)[0]
    print(
        f"  busiest {busiest[0]} with {busiest[1]} turns "
        f"({busiest[1] / len(turns):.0%} of all)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

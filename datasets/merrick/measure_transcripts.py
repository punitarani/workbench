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


# What this firm says when it names a near date, and the token each form
# normalises to. First match wins, so order matters: `end of the day` has
# to be tried before anything that could claim `day` on its own.
#
# **This is the measurement's definition of a deadline, and a task's
# admitted forms have to be the same set.** They were not, which is why
# this constant exists at all. The screen shipped matching weekdays only,
# because the first draft of the commitment task admitted weekdays only.
# The brief then widened to admit the relative forms -- because the corpus
# writes far more of them -- and this screen never followed. Measured over
# 56 recorded days of the v6 world: `eod` and its spellings appear in 245
# turns, `tomorrow` in 201, and every weekday combined in 169. So a
# weekday-only screen was reporting the supersession rate of about an
# eighth of the deadline material and printing it as the corpus's.
DEADLINE_FORMS: tuple[tuple[str, str], ...] = (
    (r"\b(?:EOD|COB|close of business|end of (?:the )?day)\b", "eod"),
    (r"\b(?:EOW|end of (?:the )?week)\b", "end of week"),
    (r"\btomorrow\b", "tomorrow"),
    (r"\bMonday\b", "monday"),
    (r"\bTuesday\b", "tuesday"),
    (r"\bWednesday\b", "wednesday"),
    (r"\bThursday\b", "thursday"),
    (r"\bFriday\b", "friday"),
)

_DEADLINE = tuple((re.compile(p, re.IGNORECASE), token) for p, token in DEADLINE_FORMS)

# Above this share of Title-Case words, a description is a sentence rather
# than a name and yields no usable handle. See `_matter_handles`.
_TITLE_CASE = 0.6


def _deadline(text: str) -> str | None:
    """The first admitted deadline form in a turn, normalised to its token.

    First match wins rather than collecting every form the turn contains,
    because "EOD tomorrow at the latest" names one deadline in two
    phrasings. Collecting both would make a single sentence look like a
    speaker disagreeing with themselves, and supersession below is measured
    by comparing a speaker's first statement to their last -- so a fake
    disagreement inside one turn would be counted as a real revision.
    """

    for pattern, token in _DEADLINE:
        if pattern.search(text or ""):
            return token
    return None


def _matter_handles(state: Path) -> tuple[dict[str, str], list[str], list[str]]:
    """Every matter that can be named out loud, by the word people say.

    Read from the served matter list. This screen used to carry a literal
    tuple of twenty client and matter names, and by the time the v6 world
    was recorded two of them -- `Hartley` and `Nordholm` -- named no matter
    this firm had, while `Pryor`, the third-busiest handle in the corpus at
    102 turns, was missing from it entirely.

    That is worse here than the same drift would be in a solver. The figure
    this feeds is the gate that decides whether a transcript task is viable
    at all, so a literal that drifts does not produce one wrong row
    somewhere downstream: it produces a confident viability verdict that
    nobody re-checks, because consulting the gate is what people do
    *instead of* looking.

    A handle is a proper noun from the matter's own description -- the part
    after the client name, which is what gets said in a room. Nobody says a
    display number: no turn in 56 recorded days contains one.

    Two kinds of description yield nothing usable, and are reported rather
    than guessed at:

    * **Title Case.** The matters the engine mints mid-run are described
      with a status sentence instead of a name -- `Priyanka Sandhurst
      Clearance Confirmation Pending` -- and every capitalised word in one
      looks like a proper noun. Taking handles from those yields `Good`,
      `Standing`, `Action` and `Break`, which match ordinary prose and
      would attach commitments to a matter nobody mentioned.
    * **No proper noun at all.** `regulatory inquiry`, `pro bono`,
      `administration`. There is no word a speaker can say that picks these
      out and nothing else.

    A handle two matters claim is dropped rather than assigned to either.
    After the engine minted `00033` and `00034` mid-run, `Sandhurst` named
    four different matters at once, so a turn saying it names none of them
    uniquely -- and a task keyed on the matter cannot grade those turns no
    matter how well they are read.
    """

    path = state / "clio.db"
    if not path.is_file():
        raise SystemExit(
            f"no clio.db under {state}. Matters are read from the served "
            "list rather than named here, so without it this screen has "
            "nothing to group a speaker's commitments by."
        )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = connection.execute(
        "SELECT display_number, description FROM matters"
    ).fetchall()
    connection.close()
    if not rows:
        raise SystemExit(
            "clio.db serves no matters. Every figure below would be a "
            "confident zero computed over an empty list."
        )

    claimed: dict[str, set[str]] = collections.defaultdict(set)
    unreachable: list[str] = []
    for display, description in rows:
        parts = description.split(" - ")
        tail = parts[1] if len(parts) > 1 else parts[0]
        words = re.findall(r"[A-Za-z][\w'-]*", tail)
        # ALL-CAPS is an acronym (`OEM`, `WIP`), not evidence of a Title-Case
        # sentence; counting it as one hid `Fairmont` behind `OEM`.
        titled = [w for w in words if re.fullmatch(r"[A-Z][a-z'-]+", w)]
        if not words or len(titled) / len(words) > _TITLE_CASE:
            unreachable.append(display)
            continue
        nouns = [w for w in titled if len(w) >= 4]
        if not nouns:
            unreachable.append(display)
            continue
        for noun in nouns:
            claimed[noun.lower()].add(display)

    handles = {h: next(iter(m)) for h, m in claimed.items() if len(m) == 1}
    ambiguous = sorted(h for h, m in claimed.items() if len(m) > 1)
    return handles, ambiguous, sorted(unreachable)


def _supersession(turns: list, meetings: dict, handles: dict[str, str]) -> None:
    """Does a date said in one room get changed in a later one?

    This is the only mechanism in this project's ledger ever measured to
    move a frontier model off ceiling -- *a second statement inside a unit
    the reader has already resolved* -- so whether the corpus contains it
    decides whether a transcript task has anything to be hard about.

    The first guess about where to find it was wrong in a way worth
    keeping. **Within** a single meeting it essentially does not happen: a
    meeting here is a five-turn one-pass status round and nobody revises
    inside it. A screen for revision *cues* ("actually", "instead", "moved
    to") fired on a third of meetings and was almost entirely false --
    those turns are a chair moving through an agenda. **Across** the
    recurring series it is common, and that is the thing worth grading: a
    commitment made in one docket call and quietly replaced in a later one,
    which no single meeting reveals.

    The rate is printed rather than quoted here, because every number this
    docstring used to carry was measured on a world that has since been
    re-recorded, and a stale figure in a docstring is exactly the failure
    this file was rewritten to stop repeating.
    """

    if not handles:
        print("\nsupersession — no matter has a sayable handle; cannot group")
        return
    pattern = re.compile(
        "|".join(rf"\b{re.escape(h)}\b" for h in handles), re.IGNORECASE
    )
    track: dict[tuple[str, str], list] = collections.defaultdict(list)
    for meeting_id, position, speaker, text in turns:
        day = _deadline(text or "")
        if day is None:
            continue
        for handle in {m.lower() for m in pattern.findall(text or "")}:
            track[(speaker, handles[handle])].append(
                (meetings[meeting_id][1], position, meeting_id, day)
            )

    occasions = {key: sorted(seq) for key, seq in track.items()}
    repeated = {
        key: seq for key, seq in occasions.items() if len({row[2] for row in seq}) >= 2
    }
    changed = sum(1 for seq in repeated.values() if seq[0][3] != seq[-1][3])
    print("\nsupersession — is a date said once changed later?")
    print(f"  (speaker, matter) pairs naming a deadline at all     {len(track):5d}")
    print(f"  named in two or more separate meetings               {len(repeated):5d}")
    share = changed / len(repeated) if repeated else 0.0
    verdict = (
        "   <-- ABSENT: nothing is ever superseded, so a reader who takes "
        "the first answer is never wrong"
        if share < 0.15
        else ""
    )
    print(
        f"  ...and the deadline DIFFERS by the last              {changed:5d} "
        f"({share:.0%}){verdict}"
    )

    # A key field with a dominant value has a floor a reader can reach
    # without reading: answer the mode everywhere and collect its share.
    # Measured because it is invisible in the rate above -- a corpus can
    # supersede constantly and still be guessable, if what it supersedes
    # *to* is nearly always the same token.
    live = collections.Counter(seq[-1][3] for seq in occasions.values())
    if live:
        token, count = live.most_common(1)[0]
        print(f"\n  live deadlines by token: {dict(live.most_common())}")
        print(
            f"  guessing {token!r} on every row scores "
            f"{count / sum(live.values()):.0%} of the day field with no reading"
        )


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

    handles, ambiguous, unreachable = _matter_handles(STATE)
    print("\nwhich matters can be named out loud?")
    print(f"  matters with a handle a speaker can say  {len(handles):4d}")
    print(
        f"  handle claimed by two or more matters    {len(ambiguous):4d}  {ambiguous}"
    )
    print(
        f"  no sayable handle at all                 {len(unreachable):4d}"
        "  (status-sentence or common-noun descriptions)"
    )
    print(
        "  a commitment about any of those cannot be keyed to a matter, "
        "however well it is read"
    )

    _supersession(turns, meetings, handles)

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

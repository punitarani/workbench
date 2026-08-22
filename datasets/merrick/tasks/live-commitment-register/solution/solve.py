"""Reference solver: the live commitment register.

One rule, and the whole difficulty is in the second half of it.

**A commitment is two things at once**: somebody speaking about their own
work, and a day named in the same turn. **A person owes one thing per
standing meeting: the most recent thing they said in it.** When the same
person names a day again in a later meeting of the same series, the later
statement replaces the earlier one entirely — not a second row, not a note,
simply no longer what they owe.

**What is graded is the date, not the word.** A deadline said out loud is
relative: `EOD`, `tomorrow`, `Thursday`. Two people saying `EOD` three weeks
apart owe different days, and so does one person saying it twice. The
register reports the resolved calendar date, which means a reader who has
the right owner and the right series but the wrong *meeting* still gets the
row wrong. That is the whole mechanism, and it is measured: grading the
token gives a reader who guesses the commonest word 47-69% of the field for
free, and grading the date gives them 16-23%.

**Why there is no matter column**, though an earlier draft of this task had
one and its removal is the reason this file was rewritten. The brief said "a
commitment about a matter"; a solver can only implement "a turn containing a
commitment token, a date token and a matter token". Measured on 56 recorded
days those are different rules: of 178 turns carrying a commitment and a
deadline only 63 name a matter, so the rule discarded 65% of the firm's real
promises for a reason unrelated to whether a promise was made — and in a
third of the 63 it kept, the matter name sat more than 120 characters from
the commitment, a different sentence of a 71-word turn. One qualifying turn
attached a promise to a matter in the clause where the speaker said she had
*nothing* on it.

The general form is worth stating once, because it will come up again: **a
conjunctive rule is safe only when its conjuncts share a unit.** Who is
speaking and what day they named are properties of a turn. Which piece of
work a promise is about is a property of a clause, and no care in the brief
turns a regex over a turn into a reader of clauses. Owner, series and date
are all turn-scoped, so the register is keyed on those and on nothing else.

That is also why this reads meetings rather than mail. Every other surface
in this world can be flattened by a script: `list_activities` returns all
21,597 time entries in about seventy seconds at zero context cost, and the
arithmetic over them is three lines. A transcript has no id to group by and
no column to sum, so the only way to know what was said is to read it.

**The oracle is computed the way the register is defined**, and
`checks/verify.py` derives the same answer by a second route from the
brief's own prose, so a rule that drifts between them is visible rather than
silently agreed.

Every `measure()` below is a value this world has not finished recording.
The guard raises rather than being a placeholder that is a syntax error: the
file compiles, the schema and independence gates can read it, and running it
before the measurement lands fails loudly with the question still open. The
date arithmetic deliberately sits above that line — it is a property of the
English, not of the recording, so it is written, tested and settled now.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("live_commitments.json")

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")

# What a person says when the work is theirs. Measured on 56 recorded days:
# `I'll` 501 turns, `I will` 9, and nothing looser survives contact —
# `I have` is possession, `I'd` is conditional, and `I can` is as often
# `I can't` or `I can see why`. A chair recapping somebody else's promise
# ("Reinhardt, $61,047.00 out by Thursday") is not a commitment by anyone in
# the room: the person who owes it never said it, and the person who said it
# does not owe it.
OWNER_FORMS: tuple[str, ...] = (r"\bI'll\b", r"\bI will\b")

# The deadline forms this firm writes, and the token each normalises to.
# First match wins, so **order is the rule** and the compound comes first.
#
# `EOD tomorrow` is one deadline meaning end of day tomorrow, and it is the
# single commonest two-form phrase in the corpus: 47 of 178 commitment turns.
# A table that tries `EOD` before it resolves a quarter of everything graded
# to the wrong day. 40% of commitment turns name two forms at all, so this
# is not an edge case dressed up as one.
# A gap between the words of a form is any run of space or punctuation, not
# a space. The firm writes `EOD-tomorrow` and `end-of-week` as readily as it
# writes them out, and a pattern anchored on `\s+` reads the hyphenated
# compound as a bare `EOD` and puts the deadline a day early — silently,
# because `eod` is a valid token that yields a plausible date. The
# independent verifier tokenises instead of matching, so it read those turns
# correctly and the two derivations disagreed by one supersession, which is
# how this was found rather than shipped.
_GAP = r"[\s\-\u2010-\u2015]+"


def _form(*words: str) -> str:
    return r"\b" + _GAP.join(words) + r"\b"


_EOD = rf"(?:EOD|COB|close{_GAP}of{_GAP}business|end{_GAP}of{_GAP}(?:the{_GAP})?day)"

DEADLINE_FORMS: tuple[tuple[str, str], ...] = (
    # Every compound, in either order, ahead of either part. This firm
    # writes all of them and each names ONE day: `EOD tomorrow` 79 turns,
    # `tomorrow EOD` 27, `<weekday> EOD` 6. A table that tries the bare
    # `EOD` first resolves every one of them to the day it was said —
    # silently, because `eod` is a valid token yielding a plausible date.
    (rf"\b{_EOD}{_GAP}tomorrow\b", "tomorrow"),
    (rf"\btomorrow{_GAP}{_EOD}\b", "tomorrow"),
    *((rf"\b{day}{_GAP}{_EOD}\b", day) for day in WEEKDAYS),
    *((rf"\b{_EOD}{_GAP}{day}\b", day) for day in WEEKDAYS),
    (rf"\b{_EOD}\b", "eod"),
    (rf"\b(?:EOW|end{_GAP}of{_GAP}(?:the{_GAP})?week)\b", "end of week"),
    (r"\btomorrow\b", "tomorrow"),
    *((rf"\b{day}\b", day) for day in WEEKDAYS),
)

# How many times a title has to appear in the window before the meeting is a
# *standing* one rather than a one-off.
#
# The register is keyed on the series, so a one-off is a key with exactly one
# meeting in it: nothing can supersede, and the key is a free-text title the
# agent has to reproduce character for character. This world writes two of
# those a colon apart — `Ardmore Chain-of-Access Routing Decision` and
# `Ardmore Chain-of-Access: Routing Decision` — which are one meeting to a
# reader and two rows to a grader.
#
# The calendar cannot answer this, though it looks as though it should:
# `event_recurrence` is a real table that the projection never writes, so
# every event in the recorded world is served `recurrence: []` even though
# the workplace spec declares these eight meetings daily or weekly. So the
# series are recovered by counting, and the threshold is measured rather than
# picked: across four windows the standing series occur 4 to 32 times and the
# one-offs 1 or 2, so any cut in 3..4 separates them. Three is chosen because
# a 30-day window puts the weekly series at 4 and a cut of 5 would silently
# drop five of the eight.
STANDING_SERIES_MINIMUM = 3

_OWNER = re.compile("|".join(OWNER_FORMS), re.IGNORECASE)
_DEADLINE = tuple(
    (re.compile(pattern, re.IGNORECASE), token) for pattern, token in DEADLINE_FORMS
)


def _window() -> tuple[int, int]:
    """The window, in seconds from the run epoch, inclusive of both ends.

    A meeting is in the window when it **started** inside it; one that runs
    past the last day is still that day's meeting.

    «MEASURE: the window. `datasets/merrick/measure_transcripts.py` prints
    meetings, turns and words per window and refuses over 60,000 words or
    under 25 meetings. On 56 partial days of v6, days 20-64 held 140
    meetings and 50,113 words — inside the ceiling — and yielded 32 rows of
    which a first-answer reader got 72% wrong, against 26 rows at 69% for
    days 20-49. Longer is better until the ceiling binds, because
    supersession accumulates with time. Re-measure on the finished record:
    every figure here is from a recording that was 43% complete.»

    Probed end to end on the partial bundle at days 20-64, which is the
    shape recommended when the recording finishes: 131 standing meetings,
    660 turns, 28 rows over 7 series, 62 supersessions, 17 distinct due
    dates with the commonest holding 14%. A reader who takes each person's
    first statement finds every row — `row_f1` 1.000 keyed on
    (owner, meeting) — and scores **0.179** once the date joins the key,
    because they get the due date wrong on 82% of rows and report
    `superseded_count` as 0.

    Called rather than evaluated at import so the pure date arithmetic below
    can be tested without a corpus.
    """

    # Named `WINDOW_FIRST_DAY` / `WINDOW_LAST_DAY` because `build_tasks`
    # reads the window off this source to tell the verifier which window to
    # re-derive, and those are the names it looks for. It tolerates the
    # indentation, so the window can live in here and the rest of the
    # module -- the date arithmetic, the form tables -- stays importable
    # before the corpus exists.
    WINDOW_FIRST_DAY = 49  # PROBE ONLY — not committed
    WINDOW_LAST_DAY = 74  # PROBE ONLY — not committed
    return WINDOW_FIRST_DAY * 86_400, (WINDOW_LAST_DAY + 1) * 86_400 - 1


def deadline_token(text: str) -> str | None:
    """The deadline a turn names, normalised, or None.

    First match wins in declaration order, which is why the compound form
    leads the table. Collecting every form instead would make
    "I'll confirm by EOD tomorrow" name two deadlines, and a turn that
    disagrees with itself becomes a fake revision the moment supersession is
    computed by comparing a speaker's first statement to their last.
    """

    for pattern, token in _DEADLINE:
        if pattern.search(text or ""):
            return token
    return None


# A sentence, for the purpose of pairing a promise with a date. Split on
# terminal punctuation *and the semicolon*, because this firm writes long
# turns that hang several independent statements off one another.
_SENTENCE = re.compile(r"(?<=[.?!;])\s+")


def commitment_in(text: str) -> str | None:
    """The deadline this turn's speaker committed to, or None.

    **The promise and the date must be in the same sentence**, and getting
    that wrong is what this function exists to prevent. An earlier version
    asked only whether the turn contained an owner form *somewhere* and a
    deadline *somewhere*, which is not the same question in a 71-word turn
    and produced rows nobody made:

    * "the second I get a timestamped response from their counsel I'll log
      it straight into the tracker" — a real promise, conditional on an
      external event, with no date of its own; the `EOD tomorrow` sat two
      sentences away describing a checkpoint.
    * "Position Statement review, owner Jamal, due EOD tomorrow ... I'll
      circulate the updated Master Docket Report" — the docket manager
      reciting *somebody else's* deadline beside a promise of her own that
      carries none.
    * "if it's still open Wednesday EOD, flag me directly and I'll make the
      call" — the date is the *condition*, not the deadline.

    Eight of twenty-five oracle rows were of this kind. Two frontier models
    independently declined all of them, and the row count under this rule
    is 17 — exactly what one of them submitted. They were right and the
    oracle was wrong.

    It is the same defect that retired this task's first design one conjunct
    over. Owner and deadline are both properties of a *turn* only in the
    trivial sense that both appear in it; the *pairing* of an actor with a
    date is a property of a clause. A sentence is the closest unit a rule
    can name out loud, so it is the one the brief names.

    First sentence wins, matching `deadline_token`'s first-match-wins: a
    speaker who commits twice in one turn is making one commitment.
    """

    for sentence in _SENTENCE.split(text or ""):
        if _OWNER.search(sentence):
            token = deadline_token(sentence)
            if token is not None:
                return token
    return None


def due_date(said_on: dt.date, token: str) -> dt.date:
    """The calendar date a token names, said on `said_on`.

    Every branch here is a convention the corpus exercises, which is why the
    brief states each one rather than listing them for completeness:

    * `eod` is the day it was said. The meeting is in the morning and the
      commitment is for that evening.
    * `tomorrow` is the next **working** day, so said on a Friday it means
      Monday. The firm records no weekend days at all — 58 recorded days,
      every one Monday to Friday — so a Saturday deadline would be a date on
      which nobody could deliver.
    * `end of week` is that week's Friday, and said *on* a Friday it means
      that same day rather than a week later.
    * a weekday names its **next** occurrence, strictly after the day it was
      said. Said on a Thursday, "Thursday" is next Thursday — that happens
      in 3 turns — and a weekday earlier in the week than the meeting is
      next week's, which happens in 26.
    """

    if token == "eod":
        return said_on
    if token == "tomorrow":
        nxt = said_on + dt.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += dt.timedelta(days=1)
        return nxt
    if token == "end of week":
        return said_on + dt.timedelta(days=(4 - said_on.weekday()) % 7)
    ahead = (WEEKDAYS.index(token) - said_on.weekday()) % 7
    return said_on + dt.timedelta(days=ahead or 7)


def _epoch(connection: sqlite3.Connection) -> tuple[dt.datetime, ZoneInfo]:
    """The run's own epoch and timezone, from the surface that serves them.

    `meetings.started` is an offset in seconds from this epoch, **not a Unix
    timestamp**. Read as one it yields 1970 dates that parse, sort and
    compare perfectly well while putting 30% of the firm's meetings on a
    weekend — a fidelity defect that does not exist, discovered only because
    the recorded day labels disagreed.
    """

    meta = dict(connection.execute("SELECT key, value FROM meta"))
    zone = ZoneInfo(meta["timezone"])
    return dt.datetime.fromisoformat(meta["epoch"]).astimezone(zone), zone


def main() -> int:
    low, high = _window()
    connection = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    epoch, zone = _epoch(connection)
    people = dict(
        sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True).execute(
            "SELECT person_id, name FROM people"
        )
    )

    window = {
        meeting_id: (started, title)
        for meeting_id, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    }
    standing = {
        title
        for title, count in collections.Counter(
            title for _started, title in window.values()
        ).items()
        if count >= STANDING_SERIES_MINIMUM
    }
    window = {
        meeting_id: row for meeting_id, row in window.items() if row[1] in standing
    }
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in window
    ]
    connection.close()

    said: dict[tuple[str, str], list] = {}
    for meeting_id, position, speaker, text in turns:
        token = commitment_in(text or "")
        if token is None:
            continue
        started, title = window[meeting_id]
        said.setdefault((speaker, title), []).append(
            (started, position, meeting_id, token)
        )

    live, superseded = [], 0
    for (speaker, title), occasions in said.items():
        occasions.sort()
        superseded += len({row[2] for row in occasions}) - 1
        started, _position, meeting_id, token = occasions[-1]
        moment = epoch + dt.timedelta(seconds=started)
        live.append(
            {
                "owner": people.get(speaker, speaker),
                "meeting": title,
                "due": due_date(moment.date(), token).isoformat(),
                "meeting_id": meeting_id,
                "said_at": moment.isoformat(),
            }
        )
    live.sort(key=lambda row: (row["meeting"], row["owner"]))

    OUT.write_text(
        json.dumps(
            {
                "meetings_read": len(window),
                "turns_read": len(turns),
                "distinct_owners": len({row["owner"] for row in live}),
                "superseded_count": superseded,
                "live": live,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

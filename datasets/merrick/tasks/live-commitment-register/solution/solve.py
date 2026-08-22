"""Reference solver: the live commitment register.

One rule, and the whole difficulty is in the second half of it.

**A commitment is three things at once.** Somebody speaking about their own
work, a matter named in the same turn, and a day named in the same turn.
Any two of the three is not a commitment: a chair assigning work names a
matter and a day and promises nothing, and a question names both and
promises less.

**A person owes one thing per matter: the most recent thing they said.**
When the same person names a day for the same matter in a later meeting,
the later statement replaces the earlier one entirely. The earlier one is
not a second row and not a note — it is simply no longer owed. Ordering is
by when the *meeting* started, not by position in a transcript, because two
turns in different rooms have no relative position.

That is why this reads meetings rather than mail. Every other surface in
this world can be flattened by a script: `list_activities` returns all
21,597 time entries in about seventy seconds at zero context cost, and the
arithmetic over them is three lines. A transcript has no id to group by and
no column to sum. A commitment made out loud is not a field, so the only
way to know what was said is to read what was said — which is the one
property in this world that a shell cannot defeat.

**The oracle is computed the same way the register is defined**, and that
is deliberate: `checks/verify.py` derives the same answer by a second route
from the brief's own prose, so a rule that drifts between the two is
visible rather than silently agreed.

Every «MEASURE» below is a value this world has not finished recording. The
guard is a call that raises rather than a placeholder that is a syntax
error: the file compiles, the schema and independence gates can read it,
and running it before the measurement lands fails loudly with the question
still outstanding.
"""

# ---------------------------------------------------------------------------
# STOP — DO NOT FILL THE `«MEASURE»` VALUES IN THIS FILE.
#
# The three-part rule this solver implements is not gradeable on the corpus
# it was written for, measured on 56 recorded days of v6 before any value
# was filled. Of 178 turns carrying a first-person commitment and a
# deadline, only 63 also name a matter: the rule discards 65% of the firm's
# real commitments for a reason unrelated to whether a commitment was made,
# and the discarded ones are the clearest in the record ("I'll have the
# statement of facts to Bennett by tomorrow night").
#
# Of the 63 it keeps, the matter name sits a median 96 characters from the
# commitment and in a third of them more than 120 -- a different sentence of
# a 71-word turn. One qualifying turn attaches a commitment to a matter in a
# clause where the speaker says she has nothing on it.
#
# The brief says "a commitment about a matter". This file can only implement
# "a turn containing a commitment token, a date token and a matter token".
# Over 71-word turns those are different rules, and an agent reading
# correctly would be graded wrong -- a task measuring agreement with a regex
# artefact and reporting it as model failure.
#
# The rule is only safe when its conjuncts share a unit. Speaker and
# deadline are properties of the turn; which matter a promise is about is a
# property of a clause.
#
# The measured reframe -- key on (speaker, meeting series) instead, which
# drops the ungradeable conjunct and roughly doubles both the rows and the
# supersession -- is in docs/fidelity/task-viability.md, together with the
# one objection that still has to be answered (the live deadline is `eod`
# for 77% of rows, so guessing beats careful-but-naive reading).
# ---------------------------------------------------------------------------

# ruff: noqa: E501
# Long lines are the «MEASURE» questions, written out in full.

import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pending import measure  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("live_commitments.json")

# The window, as zero-based day indices on the simulation clock. A meeting
# is in scope when it STARTED inside the window; one that runs past the
# last day is still that day's meeting.
#
# «MEASURE: the window. `datasets/merrick/measure_transcripts.py` prints
# meetings, turns and words per window and refuses over 60,000 words or
# under 25 meetings. On the world this was designed against, 30 calendar
# days held 123 meetings, 622 turns and 43,779 words and scored a
# first-answer reader at 0.687; 45 days went over the word ceiling. Pick
# the longest window that stays under it, because supersession accumulates
# with time and the score falls as it does.»
WINDOW_FIRST_DAY = measure("zero-based day index of the window's first working day")
WINDOW_LAST_DAY = measure("zero-based day index of the window's last working day")

# What a person says when they are taking work on themselves, as opposed to
# handing it out or asking about it. Matched case-insensitively against the
# turn's text.
#
# «MEASURE: the owner-shaped phrasings this corpus actually writes, with a
# count for each. The screen's `commitment` shape fired in 95% of meetings
# on the previous world using `I'll / I will / I can / I am going to`, but
# that is a screen rather than a rule — count each form here and admit only
# the ones the corpus writes often enough to matter. A form that occurs
# twice is a key in `form_counts` that is a constant.»
OWNER_FORMS: tuple[str, ...] = (
    measure("owner form 1"),
    measure("owner form 2"),
)

# What a deadline can look like, and this is the line the world moved
# under.
#
# The first version admitted weekdays only, on a v1 measurement: 27% of
# meetings named a weekday against 2% naming a month and a number, so
# dated deadlines would grade nearly nothing. Measured again on 26 days of
# the re-recorded world, the weekday rate had **halved to 14%** while every
# other conjunct held — owner phrases 0.86x, matter mentions 1.21x — and
# the three-part rule collapsed from 37 qualifying turns to 10. Six rows,
# under the twelve-row floor, and not one supersession that changed a day.
# The task's whole mechanism would have been absent.
#
# What the corpus writes instead is the relative form: 243 turns carry
# "end of week", "EOD", "COB" or "tomorrow" against 83 naming a weekday.
# Admitting both gives 31 rows on v6 with 32% of them superseded to a
# different deadline — healthier than v1's weekday-only 27 rows at 11%.
#
# Two forms must therefore be normalised to one token before comparison,
# and the brief has to say so: `EOD` and `COB` and "end of the day" are one
# deadline, not three. That normalisation is the rule, and a reader who
# treats them as distinct reports three live commitments where there is
# one.
#
# «MEASURE: the admitted deadline forms on the finished record, with a
# count for each and the normalisation the brief states. Include the
# relative forms; the weekday-only rule is measured dead on v6. A form
# occurring under ~15 times is a key that grades nothing.»
DEADLINE_FORMS: tuple[tuple[str, str], ...] = (
    measure("deadline form 1 as a regex, and the token it normalises to"),
    measure("deadline form 2 as a regex, and the token it normalises to"),
)

# «MEASURE: whether a turn naming two different weekdays occurs, and what
# to do with it. On the previous world it was rare enough to take the
# earliest named and say so in the brief; if v6 writes it often, the brief
# owes the reader a stated rule and this line owes it a measurement.»
TWO_DAYS_IN_ONE_TURN = measure(
    "how many turns name two different weekdays, and the rule the brief states for them"
)


def _matters(connection: sqlite3.Connection) -> dict[str, str]:
    """Every matter's display number, by the word people say for it.

    Read from clio rather than listed here: a literal list is a second
    source of truth about the firm's own matters, and the constant that
    drifted from the world it describes is the defect this tree has paid
    for most.

    **Not the description, and not the client.** Clio stores
    `"Coastal Meridian - regulatory inquiry"`, and one matter's description
    runs two hundred characters with three parentheticals. Nobody says that
    in a room. Measured on the previous world:

      * the client name is AMBIGUOUS — 11 of 34 client names cover two or
        more matters, `Firm` covers eight, `Pellumbra` and `Sable Ridge`
        three each — so a turn saying "Pellumbra" names no single matter;
      * the client name is also mostly UNSAID — only 10 of 34 ever appear
        in a transcript at all;
      * the distinctive word after the dash is both said and unique for
        **50 of 53** matters: Renwick, Tessaro, Ardmore, Hollstead,
        Ravenna.

    So the handle is the tail word, which is what a lawyer actually says.

    «MEASURE: the handle per matter, on the finished record, and its
    uniqueness. Three of 53 had no distinctive said word; decide whether
    those matters are out of scope or whether the brief names them another
    way, and say which in the brief — a matter an agent cannot name is a
    row it cannot report, and a task that grades one is grading the
    environment.»
    """

    handles = measure(
        "the word that names each matter in speech, per matter, and proof that no two share one"
    )
    return {str(handle).strip().lower(): str(display) for handle, display in handles}


def _deadline(text: str, forms: tuple) -> str | None:
    """The deadline a turn names, normalised, or None.

    First match wins, in the order the forms are declared, so the brief's
    table order is the tie-break for a turn naming two. That is a rule the
    brief owes the reader out loud — see the TWO_DAYS_IN_ONE_TURN
    measurement — because a reader who picks the other one reports a
    different commitment, not a wrong field.
    """

    for pattern, token in forms:
        found = pattern.search(text)
        if found:
            return token or found.group(0).lower()
    return None


def _window_bounds() -> tuple[int, int]:
    return WINDOW_FIRST_DAY * 86_400, (WINDOW_LAST_DAY + 1) * 86_400 - 1


def main() -> int:
    meetings_db = STATE / "meetings.db"
    clio_db = STATE / "clio.db"
    with sqlite3.connect(f"file:{clio_db}?mode=ro", uri=True) as clio:
        matters = _matters(clio)
    matter_pattern = re.compile(
        "|".join(re.escape(name) for name in sorted(matters, key=len, reverse=True)),
        re.IGNORECASE,
    )
    owner_pattern = re.compile(
        "|".join(re.escape(form) for form in OWNER_FORMS), re.IGNORECASE
    )
    deadlines = tuple(
        (re.compile(pattern, re.IGNORECASE), token) for pattern, token in DEADLINE_FORMS
    )

    low, high = _window_bounds()
    connection = sqlite3.connect(f"file:{meetings_db}?mode=ro", uri=True)
    in_window = {
        meeting_id: (started, title)
        for meeting_id, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    }
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in in_window
    ]
    people = {
        person_id: name
        for person_id, name in connection.execute("SELECT person_id, name FROM people")
    }
    connection.close()

    # Every commitment, in the order it was made. A person naming a day
    # twice for one matter inside one meeting is making one commitment, so
    # the sort key carries the turn's position under the meeting's start.
    made: dict[tuple[str, str], list] = defaultdict(list)
    for meeting_id, position, speaker, text in turns:
        body = text or ""
        if not owner_pattern.search(body):
            continue
        day = _deadline(body, deadlines)
        if day is None:
            continue
        named = {m.lower() for m in matter_pattern.findall(body)}
        if not named:
            continue
        started = in_window[meeting_id][0]
        for name in named:
            made[(speaker, matters[name])].append((started, position, meeting_id, day))

    live = []
    superseded = 0
    for (speaker, matter), statements in made.items():
        statements.sort()
        superseded += len(statements) - 1
        started, _position, meeting_id, day = statements[-1]
        live.append(
            {
                "matter": matter,
                "owner": people.get(speaker, speaker),
                "day": day,
                "meeting_id": meeting_id,
                "said_at": _iso(started),
            }
        )
    live.sort(key=lambda row: (row["matter"], row["owner"]))

    answer = {
        "meetings_read": len(in_window),
        "turns_read": len(turns),
        "distinct_owners": len({row["owner"] for row in live}),
        "matters_with_a_commitment": len({row["matter"] for row in live}),
        # What was found and discarded. Not derivable from `live` — the
        # rows are precisely what supersession removed — and the one figure
        # a reader who takes the first mention gets structurally wrong,
        # because they never saw a supersession and report zero.
        "superseded_count": superseded,
        "live": live,
    }
    OUT.write_text(json.dumps(answer, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _iso(seconds: int) -> str:
    """The meeting's start, in the epoch the served surfaces use.

    «MEASURE: read the epoch from the shared meta table rather than
    hardcoding it here. `tools.framework.read_epoch` is what the servers
    use, and an oracle that computes a moment a different way from the
    surface it grades is the defect this dataset has shipped twice.»
    """

    raise NotImplementedError(
        measure("the epoch conversion, read from the served meta table")
    )


if __name__ == "__main__":
    raise SystemExit(main())

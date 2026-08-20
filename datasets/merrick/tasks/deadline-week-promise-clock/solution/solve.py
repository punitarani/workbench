"""Reference solver: one week of Merrick Stanton's promises, and their clock.

Seven relative-date forms, each resolving to a calendar date, one row per
message and per resolved date, and a boolean that costs a second pass:
did the person who wrote the promise write again in the same thread on or
before the date they named.

Two things make this harder than the word-family registers, and both are
worth stating because both are why the row count is not the difficulty.

**Resolution is not recognition.** Finding `by Thursday` is the easy half;
the row is wrong unless *which* Thursday is right, and the rule is "the
next one strictly after the sent date", not "the Thursday of this week".
On the reference corpus for this shape, every trial found the first form
in a two-form message and two of nine found the second.

**The join is forward.** `followed_up` is not in the message that carries
the promise. It is in a later message in the same thread, possibly sent
after the week closed, and an agent that reads the window and stops has
every row's date right and every row's boolean wrong.

The row carries no `form` field, deliberately. Naming which of seven
forms matched, per row, hands the agent a checklist and decomposes the
judgment the task exists to measure -- the same decomposition that made
`self-review-exposure` score 1.000 three times over. `form_counts` still
needs the classification; the row does not print it.

«MEASURE: the difficulty argument. Once the window is fixed, record here
the corpus figures that justify it -- mail in the window, rows produced,
share of rows whose form is not the first form in their message, and the
share of rows whose `followed_up` is answered by a message sent *after*
the window. A window whose rows are all single-form and all answered
inside the week is a different, easier task than this docstring claims.»
"""

import calendar
import datetime
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("promise_clock.json")

# The week the brief names, as calendar dates rather than as an offset.
# The offset is derived from these below, so there is exactly one place
# the boundary is written down and `instruction.md` is a transcription of
# it rather than a second source. `verify.py` reads the dates back out of
# the brief and converts them the other way.
#
# --- measured on the recording in progress, day 12 of 130 -------------
#
# 523 messages (185 mail, 338 chat). Form-carrying messages by form:
#
#   EOD / COB / close of business   104
#   by <weekday>                     14
#   end of week                      12
#   by tomorrow                      11
#   end of month                      0
#   by <Month> <day>                  0
#   within N days                     0
#
# Three of the seven are **dead**, and one form carries three quarters of
# the hits. That is the defect this file's MEASURE notes exist to catch —
# a rule whose vocabulary was guessed admits a fraction of the real
# instances and scores the rest as hallucinations. Ashgrove's version of
# this cost 34 of 35 rows.
#
# This is 9% of the window and the litigation calendar peaks mid-quarter,
# so the dead forms may yet appear. Re-run before fixing the table; do
# not widen the rule to rescue a form the firm does not write, because
# that trades a vocabulary defect for rows nobody can find.

# «MEASURE: DISJOINT — this window must not overlap the one
# `one-sentence-two-dates` uses. Both extract the same seven forms from
# mail, so a shared window makes them one measurement reported twice:
# the base extraction is the hard part, and the extra graded facts each
# adds only widen the gap between tiers. The record holds roughly 130
# workdays; take the two windows from different months.
#
# «MEASURE: the window. Pick the Monday-to-Friday week whose mail carries
# at least twelve rows, whose `followed_up` is not constant, and whose
# `sent_date` is not constant. `measure_candidates.py --days N` prints
# date-form density per surface; run it on candidate weeks before fixing
# this, because a week chosen for its calendar position rather than its
# traffic is how a register comes out with four rows.»
# --- viability, measured on the record at 23 workdays -----------------
#
# An audit rated this task high-severity dead: "3 of 7 forms are dead, the
# dominant form needs no date arithmetic, and the forward join decides 0-3
# rows." Two of those three hold. **The third does not reproduce.**
#
#   week      rows   followed   not
#   2026-W02    12      4        8
#   2026-W03    38     20       18
#   2026-W04    26     12       14
#   2026-W05    11      3        8
#
# Eleven to thirty-eight rows in a graded week, with `followed_up` splitting
# roughly evenly. Neither the row count nor the join is degenerate, and a
# constant column would have shown up immediately in that table.
#
# What does hold, and matters:
#
#   * Three of the seven date forms never occur. The table below must be
#     narrowed to the four the firm writes, or the rule scores three
#     sevenths of its own vocabulary against nothing.
#   * `EOD`/`COB` is 62% of all form hits and resolves to the send date, so
#     most rows need no arithmetic at all. **38% require it** -- roughly ten
#     rows in a twenty-six-row week -- which is real but is not what the
#     task's name implies. Either accept that the clock is a minority of the
#     work, or bound the window to a week whose mix is richer, and say which
#     in the brief.
#
# So: this task ships, on four forms rather than seven. Re-run the table
# above on the finished record before fixing the window -- these are 23
# workdays of 130.

WINDOW_START = measure(
    "the Monday of the graded week, YYYY-MM-DD, written identically into "
    "instruction.md -- verify.py reads the week back out of the brief and "
    "refuses a disagreement"
)
WINDOW_END = measure(
    "the Friday of that same week, YYYY-MM-DD, written identically into instruction.md"
)

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
# «MEASURE: which number words this corpus actually writes after `within`.
# Count them in the window before fixing this map, and write the same list
# into the brief's table -- `verify.py` reads the list back out of that
# cell and refuses a word the solver knows and the brief never names. A
# word listed here that the firm never writes costs nothing; a word the
# firm writes that is missing here silently drops real rows, and the drop
# looks exactly like an agent's miss.»
NUMBER_WORDS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}
# Longest first, because alternation is first-match and not longest-match:
# put `six` ahead of `sixteen` and `within sixteen days` matches `six`,
# fails on `teen`, and the row disappears with nothing to show for it.
# Nothing in the list above collides today -- but the list above is a
# «MEASURE» somebody will edit, and this is what keeps that edit safe.
_COUNTS = sorted(NUMBER_WORDS, key=len, reverse=True)


def _next_weekday(sent: datetime.date, target: int) -> datetime.date:
    """The next such weekday strictly after `sent`.

    `% 7 or 7` is the whole rule: a promise `by Thursday` made on a
    Thursday is due the following Thursday, never the day it was written.
    """

    return sent + datetime.timedelta(days=(target - sent.weekday()) % 7 or 7)


def _end_of_week(sent: datetime.date, _match: re.Match) -> datetime.date:
    # Weeks run Monday to Sunday, so the Friday of the sent week is
    # always forward of or equal to the sent date on a working day.
    return sent + datetime.timedelta(days=4 - sent.weekday())


def _end_of_month(sent: datetime.date, _match: re.Match) -> datetime.date:
    return sent.replace(day=calendar.monthrange(sent.year, sent.month)[1])


def _by_date(sent: datetime.date, match: re.Match) -> datetime.date:
    month = MONTHS.index(match.group("month").lower()) + 1
    day = int(match.group("day"))
    try:
        # The year the message was sent, even where the date has gone by.
        return datetime.date(sent.year, month, day)
    except ValueError:
        # «MEASURE: whether the window carries a date that is not a date
        # -- `by February 30`, `by June 31`. If it does, the brief has to
        # say what such a message produces, because "skip it" and "clamp
        # it to the month's end" are both defensible and the task would
        # otherwise measure which one the agent guessed. The sibling task
        # `one-sentence-two-dates` settles the same question in one line
        # ("a date the calendar does not have is not a date"); if this
        # brief takes that answer, this branch drops the row instead of
        # refusing the build.»
        raise SystemExit(
            f"a message names {match.group(0)!r}, which is not a date in "
            f"{sent.year}. The brief does not say what that produces."
        ) from None


def _within(sent: datetime.date, match: re.Match) -> datetime.date:
    count = match.group("count").lower()
    days = int(count) if count.isdigit() else NUMBER_WORDS[count]
    # Calendar days. `business` is in the text and changes nothing, which
    # the brief says outright because the opposite reading is the natural
    # one and an agent cannot win an unstated choice by working harder.
    return sent + datetime.timedelta(days=days)


# Table order, and the order is load-bearing twice: it is the precedence
# the brief states for `form_counts`, and it is the order this iterates,
# so the first form to claim a date keeps it.
#
# Every multi-word form joins on `\s+` and not on a literal space: the
# brief says a run of whitespace between a form's words is the space, so
# `close of  business` over two spaces is still the form. `verify.py`
# reads the same rule off the brief and walks words rather than
# characters, which is where a literal space here would have shown up.
#
# «MEASURE: how this firm spells rows two, three and five -- three
# variants, and only the first is admitted below.
#   1. the words *before* the form: `by`, `the`, `this`, `next`.
#   2. the article *inside* it: `end of the week`, `end of the month`,
#      `end of the day`. These patterns take the bare form only. In a
#      comparable firm's mail in this repository `end of the day` appears
#      fifteen times and the bare form not once, so this is the variant
#      most likely to cost the register its rows.
#   3. the hyphenated form: `end-of-week`, `end-of-day`. A second corpus
#      here writes four of them, and `\s+` does not match a hyphen.
# Count all three in the window, then make these patterns and the brief's
# table say the same thing. Getting this wrong once admitted 1 of 35 real
# instances and scored the other 34 as hallucinations.»
#
# «MEASURE: `by Saturday` / `by Sunday`, and `by Mar 14` against
# `by March 14`. Whatever the counts say, the brief and these patterns
# have to agree, and today both name Monday-to-Friday and full month
# names.»
FORMS: tuple[tuple[str, re.Pattern[str], object], ...] = (
    (
        "by weekday",
        re.compile(
            r"\bby\s+(?:this\s+|next\s+)?(?P<weekday>" + "|".join(WEEKDAYS) + r")\b",
            re.IGNORECASE,
        ),
        lambda sent, match: _next_weekday(
            sent, WEEKDAYS.index(match.group("weekday").lower())
        ),
    ),
    (
        "end of week",
        re.compile(
            r"\b(?:by\s+)?(?:the\s+|this\s+|next\s+)?(?:end\s+of\s+week|eow)\b",
            re.IGNORECASE,
        ),
        _end_of_week,
    ),
    (
        "end of month",
        re.compile(
            r"\b(?:by\s+)?(?:the\s+|this\s+|next\s+)?(?:end\s+of\s+month|eom)\b",
            re.IGNORECASE,
        ),
        _end_of_month,
    ),
    (
        "by date",
        re.compile(
            r"\bby\s+(?P<month>"
            + "|".join(MONTHS)
            + r")\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\b",
            re.IGNORECASE,
        ),
        _by_date,
    ),
    (
        "end of day",
        re.compile(
            r"\b(?:eod|cob|end\s+of\s+day|close\s+of\s+business)\b", re.IGNORECASE
        ),
        lambda sent, _match: sent,
    ),
    (
        "within days",
        re.compile(
            r"\bwithin\s+(?P<count>\d+|" + "|".join(_COUNTS) + r")"
            r"\s+(?:business\s+)?days?\b",
            re.IGNORECASE,
        ),
        _within,
    ),
    (
        "by tomorrow",
        re.compile(r"\bby\s+tomorrow\b", re.IGNORECASE),
        lambda sent, _match: sent + datetime.timedelta(days=1),
    ),
)


def _window() -> tuple[datetime.date, datetime.date]:
    # No unmeasured-value guard here: `measure()` raises on import, so a
    # window nobody has chosen never reaches this function. A second check
    # for the string "MEASURE" would read as protection and could not fire.
    start = datetime.date.fromisoformat(WINDOW_START)
    end = datetime.date.fromisoformat(WINDOW_END)
    if start.weekday() != 0 or end.weekday() != 4 or (end - start).days != 4:
        raise SystemExit(
            f"{start} to {end} is not one Monday-to-Friday week, which is "
            "what the brief promises the reader."
        )
    return start, end


def _due_dates(body: str, sent: datetime.date) -> dict[datetime.date, str]:
    """Every date this message resolves to, each named by its first form.

    One row per message *and per due date*: two hits of `by Friday` are
    one row, `by Friday` and `EOD` are two, and two different forms
    landing on the same date are one. A dict keyed on the date says all
    three at once, and `setdefault` over the table order is the
    precedence the brief states for `form_counts`.
    """

    found: dict[datetime.date, str] = {}
    for name, pattern, resolve in FORMS:
        for match in pattern.finditer(body):
            found.setdefault(resolve(sent, match), name)
    return found


def main() -> None:
    start, end = _window()
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)

    meta = dict(gmail.execute("SELECT key, value FROM meta"))
    # Offsets from the recorded start of the record, in its own seconds.
    # `.date()` on the sum is a wall-clock read of a wall-clock offset,
    # which is what the world wrote; treating it as an absolute instant
    # and converting zones would move a message an hour across a spring
    # boundary for no reason the record supports.
    origin = datetime.datetime.fromisoformat(meta["epoch"])
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    messages = list(
        gmail.execute("SELECT message_id, thread_id, sender, time, body FROM messages")
    )

    def sent_date(when: int) -> datetime.date:
        return (origin + datetime.timedelta(seconds=when)).date()

    # Every message in the record, not only the week's: a promise made on
    # Thursday is answered by a message the following Wednesday, and a
    # thread index built from the window alone reports it unanswered.
    thread_traffic: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for _message_id, thread_id, sender, when, _body in messages:
        thread_traffic[thread_id].append((when, sender))

    def came_back(thread_id: str, sender: str, when: int, due: datetime.date) -> bool:
        return any(
            other_when > when
            and other_sender == sender
            and sent_date(other_when) <= due
            for other_when, other_sender in thread_traffic[thread_id]
        )

    rows: list[dict] = []
    forms: list[str] = []
    read = 0
    for message_id, thread_id, sender, when, body in messages:
        sent = sent_date(when)
        if not (start <= sent <= end):
            continue
        # Counted inside the window only. Requiring a figure over the whole
        # record is what makes an agent read the whole record: the bound has
        # to apply to the work and not only to the answer, or a weaker tier
        # spends its budget on six months of mail and files nothing.
        read += 1
        for due, form in _due_dates(body, sent).items():
            rows.append(
                {
                    "ref": message_id,
                    "due_date": due.isoformat(),
                    "author": people[sender],
                    "sent_date": sent.isoformat(),
                    "followed_up": came_back(thread_id, sender, when, due),
                }
            )
            forms.append(form)

    order = sorted(
        range(len(rows)), key=lambda i: (rows[i]["ref"], rows[i]["due_date"])
    )
    rows = [rows[i] for i in order]
    forms = [forms[i] for i in order]

    # Every listed form, including the ones nobody used. Emitting only the
    # forms that occur would make "does a zero belong in the object?" a
    # judgement the brief never settles, and an answer can be marked wrong
    # for guessing it either way.
    by_form: dict[str, int] = {name: 0 for name, _pattern, _resolve in FORMS}
    unanswered: dict[str, int] = defaultdict(int)
    for row, form in zip(rows, forms, strict=True):
        by_form[form] += 1
        if not row["followed_up"]:
            unanswered[row["author"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "promises_total": len(rows),
                "answered_in_time": sum(1 for row in rows if row["followed_up"]),
                "distinct_authors": len({row["author"] for row in rows}),
                "form_counts": by_form,
                # Most, then the earlier name -- `max` breaks a tie the
                # other way and the brief says earlier. `null` when nothing
                # went unanswered, which the brief says because `min` over
                # an empty mapping is an error and an agent guessing `""`
                # or `"none"` would be marked wrong for the guess.
                "most_unanswered": (
                    min(unanswered, key=lambda name: (-unanswered[name], name))
                    if unanswered
                    else None
                ),
                "promises": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

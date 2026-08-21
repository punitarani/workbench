"""A second derivation of the promise clock, read off the brief alone.

    WORKBENCH_STATE=out/merrick/bundle/state python3 checks/verify.py

The rule here is transcribed from `instruction.md` -- the prose the agent
is graded against -- and from nothing else. A verifier that borrows the
solver's expression of the rule inherits the solver's bugs and then
certifies that the two agree; two published scores in this tree were the
answer key rather than a measurement, certified exactly that way.

So this file shares no machinery with the solver. It holds no regular
expressions at all. It splits a body into words, remembers the raw text
between them, and walks those words once per form. A mistake in an
alternation cannot be made twice when the second reading never writes an
alternation, and `by March 14th` needs no rule for the ordinal suffix
because `14` and `th` are simply two different words.

Where the brief leaves more than one defensible computation, this takes
the one an arithmetic solver would not:

* **the window** is five enumerated dates and a set membership, not a
  pair of bounds compared with `<=`.
* **`by <weekday>`** starts on the day after the message and steps one
  day at a time, so "strictly after" is where the walk begins rather than
  a modular expression a reader has to trust.
* **`end of week`** walks back to that week's Monday by name and forward
  to its Friday by name: no `4 - weekday()`, no ISO calendar.
* **`end of month`** walks forward until the month turns over.
* **`by <Month> <day>`** looks the month up in a table `strftime` built,
  so the twelve names come from the C library and not from a list typed
  out here.
* **`followed_up`** asks whether *any* later message by the same author
  in the same thread landed on or before the due date -- every message
  considered, nothing bisected.
* **the form of a row** is the smallest table index among the forms that
  landed on that date, taken after every form in the table has run.

Four things the solver and the brief both rest on are derived here rather
than assumed, because their agreement is not evidence: a boundary off by
one day makes every row wrong together while every row-level check stays
green.

**The week comes out of `instruction.md`.** If the brief and the solver
name different weeks, every row is wrong and the solver still agrees with
itself perfectly. The count the brief's closing warning names is checked
against the messages this reading finds inside that week.

**The `form_counts` keys come out of the brief's table**, however many
there are, in the
brief's own order, which is also the precedence the brief states.

**The vocabulary the brief marks as variable is read off the table
cells**: which weekdays `by <weekday>` admits, which words may sit
between `by` and the weekday, which number words may follow `within`, and
whether month abbreviations count. A word the solver knows and the brief
never names is a rule the agent was never told.

**Every spelling the brief's table shows is fired at the matcher that
claims it** before a single message is read. A form the brief names and
this file cannot match would be a silent zero in `form_counts`, and no
row-level check would ever mention it.

**Where the rule can only be hardcoded, the sentence it was read off is
checked.** The table's third column cannot be parsed: `friday_of` walks
to a Friday because the cell says Friday, and nothing here reads that
cell and works the walk out. The same goes for the window's
inclusivity, the collapse of two forms onto one date, the precedence
that settles which form owns a row, the four clauses of `followed_up`,
the sort key and the tie-break. Every one of them is arithmetic in this
file *and* arithmetic in the solver, so the two agree no matter what the
brief says -- which is the one failure a second derivation cannot catch
by being a second derivation. So each is paired with the words it was
transcribed from, and a brief that stops saying them stops the run. That
pairing is the difference between a rule read off `instruction.md` and a
rule that merely once was.

It also asserts what row F1 structurally cannot show: that `("ref",
"due_date")` separates every row. A key that collapses two rows caps the
ceiling below 1.0 for a reason no agent can fix, and F1 still reads 1.000
because both sides dedupe identically.
"""

import datetime
import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
BRIEF = HERE.parent / "instruction.md"
# The build writes the oracle to `tests/`, which is the directory that
# ships to the grader. This file moved out of it — a `parents[3]` in
# here took the whole grader down when the container mounted `tests/`
# at `/tests` — so the path has to cross back.
ORACLE = HERE.parent / "tests" / "oracle.json"
DELIVERABLE = "promise_clock.json"

# How many rows the register needs before partial credit means anything.
# A policy about the task, not a count of the corpus: nothing here may
# stand in for a figure the recording has to supply.
ROW_FLOOR = 12


def fail(message: str) -> None:
    raise SystemExit(f"verify: {message}")


class Form(NamedTuple):
    """One row of the brief's table: its `form_counts` key, a walker over
    a body's words, and the spellings the audit fires at that walker."""

    key: str
    find: object
    probes: tuple


# --------------------------------------------------------------------
# Names, from the calendar rather than from a list typed here
# --------------------------------------------------------------------


def day_names() -> list[str]:
    """The seven weekday names, Monday first."""

    opening = datetime.date(2001, 1, 1)
    while opening.weekday() != 0:
        opening += datetime.timedelta(days=1)
    return [
        (opening + datetime.timedelta(days=step)).strftime("%A").lower()
        for step in range(7)
    ]


def month_names(shape: str) -> dict[str, int]:
    """`%B` spells `march`, `%b` spells `mar`. Which of the two this clock
    admits is a question the brief answers, not this file."""

    return {
        datetime.date(2001, number, 1).strftime(shape).lower(): number
        for number in range(1, 13)
    }


def counting_words() -> dict[str, int]:
    """Number words a brief might write after `within`. Only the ones the
    brief actually lists are admitted; this is the dictionary, not the
    rule."""

    spelled = "one two three four five six seven eight nine ten eleven twelve"
    values = {word: value for value, word in enumerate(spelled.split(), start=1)}
    values["a"] = 1
    values["an"] = 1
    return values


# --------------------------------------------------------------------
# Reading the brief
# --------------------------------------------------------------------


def brief_text() -> str:
    text = BRIEF.read_text(encoding="utf-8")
    pending = [line.strip() for line in text.splitlines() if "MEASURE" in line]
    if pending:
        fail(
            f"the brief still holds {len(pending)} unmeasured value(s), so it "
            "states no rule to check yet:\n  - " + "\n  - ".join(pending[:6])
        )
    if DELIVERABLE not in text:
        fail(f"the brief never names {DELIVERABLE}")
    return text


def section(text: str, heading: str) -> str:
    parts = text.split(heading, 1)
    if len(parts) != 2:
        fail(f"the brief has no {heading!r} section")
    return parts[1].split("\n## ", 1)[0]


def ticked(cell: str) -> list[str]:
    """The backticked spellings in a chunk of the brief, in written order."""

    pieces = cell.split("`")
    if len(pieces) % 2 == 0:
        fail(f"an unclosed backtick in the brief: {cell!r}")
    return [piece.strip().lower() for piece in pieces[1::2] if piece.strip()]


# --------------------------------------------------------------------
# The brief's own words, wherever this file can only hardcode the rule
# --------------------------------------------------------------------


def flattened(chunk: str) -> str:
    """A piece of the brief with its emphasis, its backticks and its line
    wrapping taken out, so a phrase can be looked for without caring how
    the paragraph happened to break."""

    return " ".join(chunk.replace("*", " ").replace("`", " ").lower().split())


def insists(where: str, chunk: str, phrases: tuple) -> None:
    """Refuse unless the brief still states the rule this file computes.

    Some of the brief is arithmetic, and no amount of reading turns an
    English sentence into arithmetic: `friday_of` walks to a Friday
    because the table's due column says Friday, not because anything here
    can read that cell and work it out. What can be checked is that the
    sentence has not moved out from under the arithmetic.

    That check is not decoration. A brief reworded to say `end of week`
    means the Sunday, or that a tie goes to the later name, leaves this
    file and the solver both computing the old rule, in perfect
    agreement: every row wrong together, and every row-level comparison
    green. This is the one failure the second derivation cannot catch by
    being a second derivation.
    """

    flat = flattened(chunk)
    missing = [phrase for phrase in phrases if flattened(phrase) not in flat]
    if missing:
        fail(
            f"the brief's {where} no longer says {missing[0]!r}, and this "
            "file hardcodes that rule rather than reading it. The two have "
            "gone apart with nothing else to show it: read the brief again "
            f"and move the derivation to match.\n  brief now: {flat[:280]}"
        )


def cell_parts(cell: str, marker: str) -> tuple[list[str], list[str]]:
    """A table cell's spellings, and the words it lists after `marker` as
    admissible alongside them -- "with or without", "one of"."""

    at = cell.lower().find(marker)
    if at < 0:
        return ticked(cell), []
    return ticked(cell[:at]), ticked(cell[at:])


def form_table(text: str) -> list[list[str]]:
    grid = []
    for line in section(text, "## What counts as a promise").splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            grid.append([cell.strip() for cell in line[1:-1].split("|")])
    if len(grid) < 3:
        fail("the brief's form table has no header, no ruler or no rows")
    header, ruler, *forms = grid
    if len(header) != 3 or set("".join(ruler)) - set("-: "):
        fail("the brief's form table is not the three-column table expected")
    # Deliberately not a fixed count. This asserted seven, which is the
    # number the table was drafted with -- and a measurement of the record
    # says three of those seven never occur and the table must narrow to
    # four. Doing the correct thing would therefore have failed here, with a
    # message blaming the brief for the change it was supposed to receive.
    #
    # What must hold is that the brief and the deliverable agree, not that
    # either matches a number this file remembers. `form_counts` is checked
    # against these rows elsewhere, so a table that grows or shrinks carries
    # the deliverable with it.
    if len(forms) < 2:
        fail(
            f"the brief names {len(forms)} form(s); a register whose rule is "
            "a closed set of forms needs at least two to be a rule"
        )
    if any(len(row) != 3 for row in forms):
        fail("a row of the brief's form table is not three cells wide")
    return forms


def week(text: str) -> list[datetime.date]:
    """The days the brief names, enumerated one by one rather than held as
    a pair of bounds."""

    stamps = []
    for token in section(text, "## The week").replace("*", " ").split():
        token = token.strip("`,.;:()[]")
        if len(token) == 10 and token[4:5] == "-":
            try:
                stamps.append(datetime.date.fromisoformat(token))
            except ValueError:
                continue
    if len(stamps) != 2:
        fail(f"the brief's week names {len(stamps)} dates; it must name two")
    days, day = [], stamps[0]
    while day <= stamps[1]:
        days.append(day)
        day += datetime.timedelta(days=1)
    named = day_names()
    if len(days) != 5:
        fail(f"{stamps[0]} to {stamps[1]} spans {len(days)} days, not five")
    if days[0].strftime("%A").lower() != named[0]:
        fail(f"the brief opens its week on {stamps[0]}, which is no Monday")
    if days[-1].strftime("%A").lower() != named[4]:
        fail(f"the brief closes its week on {stamps[1]}, which is no Friday")
    return days


def promised_volume(text: str) -> int | None:
    """The mail count the brief's closing warning names, where it names a
    single one. The brief and this reading must find the same week."""

    counts = []
    for token in section(text, "## A warning about completeness").split():
        token = token.strip(".,;:()*`").replace(",", "")
        if token.isdigit():
            counts.append(int(token))
    return counts[0] if len(counts) == 1 else None


# --------------------------------------------------------------------
# Words, and walking them
# --------------------------------------------------------------------


def split_words(body: str) -> tuple[list[str], list[str]]:
    """A body as lowercased words plus the raw text sitting before each.

    Runs of letters and runs of digits are separate words, which is why
    `14th` arrives as `14` then `th` and the brief's ordinal suffix costs
    no rule at all.
    """

    words: list[str] = []
    gaps: list[str] = []
    cursor, mark, size = 0, 0, len(body)
    while cursor < size:
        if body[cursor].isalpha():
            same = str.isalpha
        elif body[cursor].isdigit():
            same = str.isdigit
        else:
            cursor += 1
            continue
        head = cursor
        while cursor < size and same(body[cursor]):
            cursor += 1
        gaps.append(body[mark:head])
        words.append(body[head:cursor].lower())
        mark = cursor
    return words, gaps


def runs_on(gaps: list[str], index: int) -> bool:
    """True when a word follows the one before it across whitespace and
    nothing else -- the word-wise reading of the single space the brief
    writes between `end` and `of`."""

    if index == 0:
        return False
    return gaps[index] != "" and not gaps[index].strip()


def spelt(spelling: str) -> tuple[tuple, tuple]:
    """A spelling the brief shows, as its words and the joins between them.

    `end of week` joins on whitespace; `end-of-week` joins on a hyphen.
    Splitting the brief's own spelling this way is what lets the table
    decide which variants the firm writes, rather than this file guessing
    at the hyphen and the solver guessing differently.
    """

    words, gaps = split_words(spelling)
    if not words:
        fail(f"the brief shows {spelling!r} as a spelling, which has no words")
    return tuple(words), tuple(gap.strip() for gap in gaps[1:])


def sits_at(words: list[str], gaps: list[str], start: int, shown: tuple) -> bool:
    phrase, joins = shown
    if start + len(phrase) > len(words):
        return False
    for offset, wanted in enumerate(phrase):
        if words[start + offset] != wanted:
            return False
        if not offset:
            continue
        gap = gaps[start + offset]
        # "any run of whitespace between its words is the space": a join
        # the brief wrote blank wants whitespace and nothing else, and a
        # join it wrote as punctuation wants that punctuation.
        if gap == "" or gap.strip() != joins[offset - 1]:
            return False
    return True


# --------------------------------------------------------------------
# The seven forms, each matched on its own
# --------------------------------------------------------------------


def friday_of(sent: datetime.date) -> datetime.date:
    """ "the Friday of the week the message was sent, weeks running Monday
    to Sunday": back to that Monday by name, then forward to that Friday
    by name."""

    named = day_names()
    day = sent
    while day.strftime("%A").lower() != named[0]:
        day -= datetime.timedelta(days=1)
    while day.strftime("%A").lower() != named[4]:
        day += datetime.timedelta(days=1)
    return day


def month_end(sent: datetime.date) -> datetime.date:
    """ "the last calendar day of the month the message was sent": forward
    a day at a time until the month turns over."""

    day = sent
    while True:
        onward = day + datetime.timedelta(days=1)
        if onward.month != day.month:
            return day
        day = onward


def tomorrow_of(sent: datetime.date) -> datetime.date:
    return sent + datetime.timedelta(days=1)


def day_of(sent: datetime.date) -> datetime.date:
    return sent


def weekday_form(key: str, cell: str) -> Form:
    """`by Monday` ... `by Friday`, with or without `this` or `next`.

    Which weekdays are admitted is the span the cell names, so a brief
    that opens the weekend admits it here too; the words allowed between
    the opening word and the weekday are the loose words the cell lists.
    """

    named = day_names()
    shown, optional = cell_parts(cell, "with or without")
    inside = [name for name in named if name in cell.lower()]
    if not inside:
        fail(f"the brief's {key!r} row names no weekday this file recognises")
    span = named[
        min(named.index(name) for name in inside) : max(
            named.index(name) for name in inside
        )
        + 1
    ]
    heads = {
        spelling.split()[0]
        for spelling in shown
        if len(spelling.split()) == 2 and spelling.split()[1] in named
    }
    if len(heads) != 1:
        fail(f"the brief's {key!r} row does not open its spellings one way")
    head = heads.pop()
    loose = {word for word in optional if " " not in word}

    def find(words, gaps, sent):
        for index, word in enumerate(words):
            if word != head:
                continue
            step = index + 1
            if step < len(words) and runs_on(gaps, step) and words[step] in loose:
                step += 1
            if step >= len(words) or not runs_on(gaps, step):
                continue
            if words[step] not in span:
                continue
            # "the next such weekday strictly after the date the message
            # was sent": begin the day after and take the first hit.
            day = sent + datetime.timedelta(days=1)
            while day.strftime("%A").lower() != words[step]:
                day += datetime.timedelta(days=1)
            yield day

    probes = (
        tuple(spelling for spelling in shown if "<" not in spelling)
        + tuple(f"{head} {name}" for name in span)
        + tuple(f"{head} {word} {name}" for word in sorted(loose) for name in span)
    )
    return Form(key, find, probes)


def phrase_form(key: str, cell: str, resolve) -> Form:
    """A form the brief spells out whole.

    The loose words in these rows -- `by`, `the`, `this`, `next` -- sit in
    front of a phrase that already matches on its own and change no date,
    so this matches the phrase and lets them fall where they will. The
    audit still fires each of them, in case a brief ever makes one of them
    load-bearing.
    """

    shown, optional = cell_parts(cell, "with or without")
    phrases = tuple(spelt(spelling) for spelling in shown)
    if not phrases:
        fail(f"the brief's {key!r} row shows no spelling for this to match")

    def find(words, gaps, sent):
        for start in range(len(words)):
            if any(sits_at(words, gaps, start, phrase) for phrase in phrases):
                yield resolve(sent)

    probes = tuple(shown) + tuple(
        f"{word} {spelling}" for word in optional for spelling in shown
    )
    return Form(key, find, probes)


def dated_form(key: str, cell: str) -> Form:
    """`by <Month> <day>` -- `by March 14`, `by March 14th`.

    Full month names always; the three-letter abbreviations only where the
    cell shows one, which is the question the brief has to settle before
    this runs.
    """

    shown, _optional = cell_parts(cell, "with or without")
    admitted = month_names("%B")
    if not any(name in cell.lower() for name in admitted):
        fail(f"the brief's {key!r} row names no month this file recognises")
    written = {word for spelling in shown for word in spelling.split()}
    short = month_names("%b")
    if any(name in written for name in short if name not in admitted):
        admitted.update(short)
    heads = {
        spelling.split()[0]
        for spelling in shown
        if len(spelling.split()) > 1 and spelling.split()[1] in admitted
    }
    if len(heads) != 1:
        fail(f"the brief's {key!r} row does not open its spellings one way")
    head = heads.pop()

    def find(words, gaps, sent):
        for index, word in enumerate(words):
            if word != head or index + 2 >= len(words):
                continue
            if not runs_on(gaps, index + 1) or not runs_on(gaps, index + 2):
                continue
            number = admitted.get(words[index + 1])
            figure = words[index + 2]
            if number is None or not figure.isdigit() or len(figure) > 2:
                continue
            # The cell shows `by March 14th`, so letters may be welded to
            # the figure -- but only an ordinal's. `by March 14x` is not a
            # spelling the cell shows, and taking it would be reading a
            # date out of something that is not one.
            tail = index + 3
            if tail < len(words) and gaps[tail] == "":
                if words[tail] not in ("st", "nd", "rd", "th"):
                    continue
            # "that day of that month, in the year the message was sent"
            try:
                yield datetime.date(sent.year, number, int(figure))
            except ValueError:
                fail(
                    f"a message sent {sent} writes {word} {words[index + 1]} "
                    f"{figure}, a day {sent.year} does not have. The brief "
                    "does not say what such a date resolves to."
                )

    probes = tuple(spelling for spelling in shown if "<" not in spelling) + tuple(
        f"{head} {name} 14" for name in sorted(admitted)
    )
    return Form(key, find, probes)


def within_form(key: str, cell: str) -> Form:
    """`within N days` or `within N business days`.

    The number words are whichever ones the cell lists -- a vocabulary the
    solver knows and the brief never names is a rule the agent was never
    told, and this is where that shows.
    """

    shown, listed = cell_parts(cell, "one of")
    known = counting_words()
    strange = [word for word in listed if word not in known]
    if strange:
        fail(f"the brief's {key!r} row lists {strange}, which are not numbers")
    admitted = {word: known[word] for word in listed}
    if not admitted:
        fail(
            f"the brief's {key!r} row names no number words. Write them "
            "backticked, after the words 'one of', so that the rule the "
            "agent reads and the rule this checks are the same list."
        )
    shapes = [spelling.split() for spelling in shown if len(spelling.split()) > 2]
    if not shapes:
        fail(f"the brief's {key!r} row shows no spelling of the expected shape")
    opens = {shape[0] for shape in shapes}
    marks = {shape[1] for shape in shapes}
    closes = {shape[-1] for shape in shapes}
    if len(opens) != 1 or len(marks) != 1 or len(closes) != 1:
        fail(f"the brief's {key!r} row spells its two forms inconsistently")
    head, mark, tail = opens.pop(), marks.pop(), closes.pop()
    # "I can usually turn these within a day or two" carries `within a
    # day`: the brief's own example makes the singular count too.
    endings = {tail, tail.removesuffix("s")}
    stray = [
        spelling
        for spelling in shown
        if len(spelling.split()) < 3 and spelling not in endings
    ]
    if stray:
        fail(
            f"the brief's {key!r} row shows {stray}, which is neither one of "
            "its two spellings nor the word they close on"
        )
    middles = {word for shape in shapes for word in shape[2:-1]}

    def find(words, gaps, sent):
        for index, word in enumerate(words):
            if word != head:
                continue
            step = index + 1
            if step >= len(words) or not runs_on(gaps, step):
                continue
            token = words[step]
            if token.isdigit():
                span = int(token)
            elif token in admitted:
                span = admitted[token]
            else:
                continue
            step += 1
            if step < len(words) and runs_on(gaps, step) and words[step] in middles:
                step += 1
            if step >= len(words) or not runs_on(gaps, step):
                continue
            if words[step] in endings:
                # "the sent date plus N calendar days; `business` changes
                # nothing."
                yield sent + datetime.timedelta(days=span)

    probes = tuple(
        " ".join(fill if word == mark else word for word in shape)
        for shape in shapes
        for fill in ["3", *sorted(admitted)]
    )
    return Form(key, find, probes)


# Each form of the brief's table: the walker to build for it, and the
# words its "when it falls due" cell has to still carry for the date
# arithmetic paired with it above to be the arithmetic the brief states.
#
# The spellings column is read; the due column cannot be -- `friday_of`
# is a walk to a Friday because the cell says Friday, and no parser here
# turns that sentence into that walk. Pairing the two in one table is
# what keeps the unread column from drifting: a cell reworded to name the
# Sunday stops matching and the run refuses, where otherwise this file
# and the solver would go on computing the Friday in agreement.
BUILDERS = {
    "by weekday": (
        weekday_form,
        ("next", "strictly after", "the date the message was sent"),
    ),
    "end of week": (
        lambda key, cell: phrase_form(key, cell, friday_of),
        (
            "friday of the week the message was sent",
            "weeks running monday to sunday",
        ),
    ),
    "end of month": (
        lambda key, cell: phrase_form(key, cell, month_end),
        ("last calendar day of the month the message was sent",),
    ),
    "by date": (
        dated_form,
        ("that day of that month", "in the year the message was sent"),
    ),
    "end of day": (
        lambda key, cell: phrase_form(key, cell, day_of),
        ("the date the message was sent",),
    ),
    "within days": (
        within_form,
        ("the sent date plus n calendar days", "business changes nothing"),
    ),
    "by tomorrow": (
        lambda key, cell: phrase_form(key, cell, tomorrow_of),
        ("the day after the sent date",),
    ),
}


def clock(rows: list[list[str]]) -> list[Form]:
    """The brief's seven forms, in the brief's own table order, which is
    the precedence the brief states for attributing a row."""

    keys = [row[1].strip("`") for row in rows]
    if sorted(keys) != sorted(BUILDERS):
        fail(
            f"the brief's table keys {sorted(keys)} are not the seven forms "
            f"this derivation knows how to build: {sorted(BUILDERS)}"
        )
    made = []
    for key, row in zip(keys, rows, strict=True):
        build, stated = BUILDERS[key]
        insists(f"{key!r} row, in its 'when it falls due' cell", row[2], stated)
        made.append(build(key, row[0]))
    return made


def hardcoded(text: str) -> None:
    """The rest of what this file decides in Python because prose cannot
    be executed, checked against the sentences it was read off.

    Which days the window admits, when one message makes two rows rather
    than one, which of several forms owns a row, what counts as coming
    back, how the register is ordered and how its tie breaks. Each is a
    whole column of the answer, and each is written here as arithmetic
    that agrees with the solver's arithmetic whatever the brief says.
    """

    insists(
        "week",
        section(text, "## The week"),
        ("sent on or between", "inclusive", "sent inside those five days"),
    )
    insists(
        "account of what a promise is",
        section(text, "## What counts as a promise"),
        (
            "matched case-insensitively in the body",
            "one row per message and per due date",
            "resolve to the same date make one row",
        ),
    )
    insists(
        "account of coming back",
        section(text, "## What counts as coming back"),
        (
            "the same author sent another message in the same thread",
            "at a later time",
            "on or before the due date",
        ),
    )
    insists(
        "output section",
        section(text, "## What to produce"),
        (
            "including the forms that turn out to be zero",
            "listed first in the table",
            "break a tie alphabetically, earlier first",
            "if every row was answered in time, null",
            "sorted by ref and then by due_date",
            "compared as text, ascending",
        ),
    )


def audit(forms: list[Form], sent: datetime.date) -> None:
    """Fire every spelling the brief's table shows at the matcher claiming
    it, before any message is read."""

    for form in forms:
        if not form.probes:
            fail(f"the brief's {form.key!r} row offers nothing to fire")
        for probe in form.probes:
            words, gaps = split_words(f"we will have it {probe} at the latest")
            if not list(form.find(words, gaps, sent)):
                fail(
                    f"the brief's table shows {probe!r} under {form.key!r} and "
                    "this derivation cannot match it, so that spelling would "
                    "count zero with nothing else complaining"
                )


# --------------------------------------------------------------------
# The derivation
# --------------------------------------------------------------------


def derive(state: Path, days: list[datetime.date], forms: list[Form]) -> dict:
    store = state / "gmail.db"
    if not store.is_file():
        fail(f"no mail database at {store}")
    db = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    settings = dict(db.execute("SELECT key, value FROM meta").fetchall())
    if "epoch" not in settings:
        fail("the mail database carries no epoch and cannot date anything")
    origin = datetime.datetime.fromisoformat(settings["epoch"])
    directory = dict(db.execute("SELECT person_id, name FROM people").fetchall())
    mail = db.execute(
        "SELECT message_id, thread_id, sender, time, body FROM messages"
    ).fetchall()
    db.close()

    def dated(seconds: int) -> datetime.date:
        return (origin + datetime.timedelta(seconds=seconds)).date()

    # The window as five dates and a membership test. A range comparison
    # off by a day moves every row together, and no row-level check would
    # say a word about it.
    inside = set(days)

    threads = defaultdict(list)
    for _ref, thread, writer, when, _body in mail:
        threads[thread].append((when, writer))

    rows: list[dict] = []
    marks: list[str] = []
    read = 0
    for ref, thread, writer, when, body in mail:
        sent = dated(when)
        if sent not in inside:
            continue
        read += 1
        if writer not in directory:
            fail(f"message {ref} was sent by {writer}, who is in no directory")
        words, gaps = split_words(body)
        # Every form that hits, then the earliest table index landing on
        # each date: "one row per message and per due date".
        earliest: dict[datetime.date, int] = {}
        for index, form in enumerate(forms):
            for due in form.find(words, gaps, sent):
                if index < earliest.get(due, len(forms)):
                    earliest[due] = index
        for due, index in earliest.items():
            # "the same author sent another message in the same thread, at
            # a later time, on a date on or before the due date."
            answered = any(
                other == writer and later > when and dated(later) <= due
                for later, other in threads[thread]
            )
            rows.append(
                {
                    "ref": ref,
                    "due_date": due.isoformat(),
                    "author": directory[writer],
                    "sent_date": sent.isoformat(),
                    "followed_up": answered,
                }
            )
            marks.append(forms[index].key)

    seats = sorted(
        range(len(rows)),
        key=lambda seat: (rows[seat]["ref"], rows[seat]["due_date"]),
    )
    rows = [rows[seat] for seat in seats]
    marks = [marks[seat] for seat in seats]

    tally = {form.key: 0 for form in forms}
    missed: dict[str, int] = defaultdict(int)
    for row, mark in zip(rows, marks, strict=True):
        tally[mark] += 1
        if not row["followed_up"]:
            missed[row["author"]] += 1

    return {
        "messages_read": read,
        "promises_total": len(rows),
        "answered_in_time": sum(1 for row in rows if row["followed_up"]),
        "distinct_authors": len({row["author"] for row in rows}),
        "form_counts": tally,
        "most_unanswered": (
            min(missed, key=lambda who: (-missed[who], who)) if missed else None
        ),
        "promises": rows,
    }


def structural(answer: dict) -> None:
    """What row F1 cannot show, whatever the rows say."""

    rows = answer["promises"]
    if len(rows) < ROW_FLOOR:
        fail(
            f"{len(rows)} rows sits under the floor of {ROW_FLOOR}: a register "
            "this thin reads 1.000 or near nothing, with no partial credit "
            "in between. Choose a busier week."
        )
    keyed = {(row["ref"], row["due_date"]) for row in rows}
    if len(keyed) != len(rows):
        fail(
            f"('ref', 'due_date') collapses {len(rows)} rows into {len(keyed)}. "
            "The ceiling drops below 1.0 and row F1 still reads 1.000."
        )
    for field in ("followed_up", "sent_date", "author"):
        spread = {json.dumps(row[field]) for row in rows}
        if len(spread) < 2:
            fail(
                f"every row carries the same {field}. A constant column grades "
                "nothing: an agent that never looks scores full marks on it."
            )


def coherent(truth: dict, keys: list[str]) -> None:
    """The oracle's summary figures against the oracle's own rows.

    Run on the answer key rather than on the derivation above, where the
    same four checks restate the arithmetic that just produced the
    figures and could not fire. The field-by-field diff that follows
    would catch the same breakage, but it reports six disagreeing fields
    where this reports the one line that is actually inconsistent.
    """

    missing = [
        field
        for field in (
            "promises",
            "promises_total",
            "answered_in_time",
            "distinct_authors",
            "form_counts",
        )
        if field not in truth
    ]
    if missing:
        fail(f"the oracle carries no {missing}")
    rows = truth["promises"]
    if truth["promises_total"] != len(rows):
        fail(
            f"the oracle calls itself {truth['promises_total']} rows and "
            f"carries {len(rows)}"
        )
    if sorted(truth["form_counts"]) != sorted(keys):
        fail(
            f"the oracle's form_counts carries {sorted(truth['form_counts'])}; "
            f"the brief's table names {sorted(keys)}"
        )
    if sum(truth["form_counts"].values()) != truth["promises_total"]:
        fail("the oracle's form_counts does not add up to its promises_total")
    if truth["answered_in_time"] != sum(1 for row in rows if row["followed_up"]):
        fail("the oracle's answered_in_time disagrees with the rows it summarises")
    if truth["distinct_authors"] != len({row["author"] for row in rows}):
        fail("the oracle's distinct_authors disagrees with the rows it summarises")


def main() -> int:
    if "WORKBENCH_STATE" not in os.environ:
        fail("set WORKBENCH_STATE to the served state of the built bundle")
    text = brief_text()
    hardcoded(text)
    forms = clock(form_table(text))
    days = week(text)
    audit(forms, days[0])
    keys = [form.key for form in forms]
    print(f"brief: {days[0]} to {days[-1]}, forms {keys}")

    answer = derive(Path(os.environ["WORKBENCH_STATE"]), days, forms)
    structural(answer)
    stated = promised_volume(text)
    if stated is None:
        print("note: the brief's closing warning names no single mail count")
    elif stated != answer["messages_read"]:
        fail(
            f"the brief says the week holds {stated} mail messages and this "
            f"reading finds {answer['messages_read']}. One of the two has the "
            "wrong week, and every row moves with it."
        )
    print(
        f"derived: {answer['messages_read']} mail in the week, "
        f"{answer['promises_total']} rows, "
        f"{answer['answered_in_time']} answered in time"
    )

    if not ORACLE.is_file():
        fail(f"no oracle at {ORACLE}; run build_tasks.py first")
    truth = json.loads(ORACLE.read_text())
    coherent(truth, keys)
    if truth != answer:
        apart = sorted(
            field
            for field in set(truth) | set(answer)
            if truth.get(field) != answer.get(field)
        )
        fail(
            f"this derivation and the oracle disagree on {apart}. One of the "
            "two reads the brief wrongly, and the brief is what the agent is "
            "graded against."
        )
    print("the oracle agrees with an independent reading of the brief")
    return 0


if __name__ == "__main__":
    sys.exit(main())

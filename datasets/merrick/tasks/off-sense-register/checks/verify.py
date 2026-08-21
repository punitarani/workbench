"""An independent derivation of the same answer.

    WORKBENCH_STATE=out/merrick/bundle/state uv run python \
        datasets/merrick/tasks/off-sense-register/tests/verify.py

Everything below is transcribed from `instruction.md` -- the prose the agent
is graded against -- and nothing from `solution/solve.py`. Copying the
solver's expression reproduces its bug and then certifies that the two
agree; two published scores were the answer key rather than a measurement,
certified exactly that way.

Where more than one computation is defensible, this uses the one the solver
did not:

**The window is a date here, not an offset.** The instruction names a
weekday and a calendar date; the solver counts `WINDOW_DAYS * 86_400`
seconds from the epoch. Their mutual agreement would be no evidence -- a
shifted boundary makes every row wrong together while every row-level check
stays green -- so this converts each message's `time` into a wall-clock date
in the firm's own zone and compares dates. Note that the recorded epoch
carries a **fixed** `-05:00`, and New York leaves that offset on 8 March
2026: if a window ever reaches past it, the two derivations disagree near
midnight and the disagreement is the finding, not a bug in this file.

**The match is tokenised here, not a regex.** The instruction says letters,
digits and the underscore continue a word and every other character ends
one. That is what `\b` means under `re.ASCII` and it is not how this
checks it: bodies are split on non-word characters and the resulting tokens
are compared casefolded. A hyphenated compound yields the bare form either
way; a longer word containing the letters yields neither. The flag is not
optional on the solver's side: plain `\b` is Unicode-aware, and the two
derivations would then part company on a form sitting against an accented
letter -- differing in expression is the point, differing on which
characters are letters is a defect.

**The department join goes through a different surface and a different
key.** The solver reads `people` out of `gmail.db` and keys on the sender's
person id. This reads `people` out of `imanage.db` -- the surface that
actually serves the field to the agent, as `location` -- and keys on the
author's full name, which is what the deliverable prints.

**The tie-break is computed the other way round.** Highest count first, then
the alphabetically earliest name among those tied, rather than one sort on
a negated count.

It also checks the floors that no per-row criterion can see: at least twelve
rows, no graded field with one value in it, both form keys present, the full
department roster present, and a row key that does not collapse two rows
into one.

Sharing no code with the solver is not the same as being independent of it
-------------------------------------------------------------------------

A second derivation catches a mistake in an expression. It cannot catch a
rule that both derivations hold identically and neither reads. This file
used to take its vocabulary from the brief's table and then hardcode
everything the vocabulary *does*: the window's inclusivity, the direction
of the tie-break, the sort order, which form owns a message carrying both,
the roster, the boundary itself. The brief could be reworded to say that a
tie goes to the later name, or that the window excludes its last day, and
this file and the solver would both go on computing the old rule -- in
perfect agreement, every row wrong together, every row-level comparison
green. Mutation-testing the brief against the old file, twenty of
twenty-seven single-phrase rule flips went unnoticed.

So each rule that is arithmetic here is paired with the sentence it was
read off, in one table, and `insists()` refuses to run when the brief stops
saying it. Three of them are stronger than a pin, because the brief can be
parsed for the value itself rather than for the words around it:

* **the two admitted forms** are read out of the brief's table, with the
  `matches` cell required to name the same spelling as the `form` cell;
* **the form a both-forms message counts under** is read out of the
  sentence that states it, and required to be the table's first row;
* **the field names**, top level and row, are read off the brief's own
  bullets and compared with the ones checked here;
* **the boundary** is parsed back out of the brief's sentence -- the
  weekday it names must be the weekday that date falls on, and the date
  must be the one this file windows on;
* **the department roster** is read off the brief's enumeration and
  compared both ways, and then put to the directory itself.

That last one is the pin that a pin cannot finish. The brief is a
transcription of the directory, so checking this file against the brief
compares two transcriptions and a department both of them missed stays
invisible -- and stays invisible to the derivation too, unless some row
happens to land in it. A department with no rows in the window owes the
object a zero, the zero is absent, and every key that is there still
reads right. So `roster_recorded()` asks the state: "one key per
department **the directory records**" names a source, and the source is
neither transcription.

The pins run before the unbuilt gates on purpose. The corpus measurements
have not landed, so nothing below the gates can execute yet; putting the
pins first means the brief and this file are held together from the day the
brief is written, and means each pin can be shown to fail on a brief that
no longer states its rule.

`ROW_FLOOR` is the one number here that is not read off anything. It is a
policy about the task -- how many rows partial credit needs to mean
something -- and not a count of the corpus, which only the recording may
supply.
"""

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pending import measure  # noqa: E402

HERE = Path(__file__).resolve().parent
BRIEF = HERE.parent / "instruction.md"
ORACLE = HERE / "oracle.json"
# An unset variable is `Path("")`, which is the working directory and is a
# directory, so `is_dir()` alone waves it through and the run goes looking
# for `./gmail.db`.
_STATE_ENV = os.environ.get("WORKBENCH_STATE", "")
STATE = Path(_STATE_ENV)
DELIVERABLE = "word_register.json"

# --- transcribed from instruction.md ------------------------------------

# "in the firm's own time zone (New York)"
FIRM_TZ = "America/New_York"
# "an object with one key per department the directory records"
DEPARTMENTS: tuple[str, ...] = ()
# "One file in your workspace: word_register.json, with exactly these
# fields" -- in the brief's own order, checked against its bullets.
TOP_FIELDS = (
    "messages_read",
    "hits_total",
    "distinct_authors",
    "form_counts",
    "department_counts",
    "top_author",
    "hits",
)
ROW_FIELDS = ("ref", "author", "sent_date", "where")

# How many rows the register needs before partial credit means anything.
# A policy about the task, not a count of the corpus.
ROW_FLOOR = 12

# Letters, digits and the underscore continue a word; everything else ends
# one.
_SPLIT = re.compile(r"[^0-9A-Za-z_]+")
# A question the corpus has not answered yet, and the words inside it are
# replaced wholesale when it does.
_PLACEHOLDER = re.compile(r"«[^»]*»", re.DOTALL)
# A bullet naming a field. Markdown admits `-`, `*` and `+` and any
# nesting width, and a formatter picks whichever it likes: keying on one
# marker and a two-space indent makes a reformat that changes no word
# read as a brief that names no fields at all. Depth is what separates a
# top-level field from a row field, so indentation is measured, not
# matched. Department keys, which are Capitalised, do not answer to
# `[a-z_]+` and so cannot be mistaken for either.
_BULLET = re.compile(r"^([ \t]*)[-*+][ \t]+`([a-z_]+)`", re.M)

# The sentences the parsed values are pulled out of, named once so the
# parser and the pin cannot drift apart.
BOUNDARY = "on or before"
BOTH_FORMS = "counts once, under"
ROSTER = "The keys are exactly, and in this spelling:"
# The same marker, found in text that still has its line breaks: the
# sentence wraps in the brief, so a plain `find` for it never matches
# there. The enumeration under it has to be read line by line, so the
# marker has to be located line by line too.
_ROSTER_AT = re.compile(r"\s+".join(map(re.escape, ROSTER.split())))


def fail(message: str) -> str:
    raise SystemExit(f"off-sense-register: {message}")


def transcribed_last_day() -> str:
    """The window's inclusive last day, as `YYYY-MM-DD`.

    Deliberately a call that raises rather than a bare constant: the module
    still imports, so the brief pins above it run and can be exercised
    before the corpus exists, and `build_tasks.py` still sees a live
    `measure()` and refuses to stage the task. `stated_boundary()` reads
    the same day back off the brief and refuses if the two differ.
    """

    return measure("the same boundary instruction.md states, as YYYY-MM-DD")


# --- reading the brief ---------------------------------------------------


def brief_text() -> str:
    if not BRIEF.is_file():
        return fail(f"no brief at {BRIEF}")
    text = BRIEF.read_text(encoding="utf-8")
    if DELIVERABLE not in text:
        return fail(f"the brief never names {DELIVERABLE}")
    return text


def section(text: str, heading: str) -> str:
    parts = text.split(heading, 1)
    if len(parts) != 2:
        return fail(f"the brief has no {heading!r} section")
    return parts[1].split("\n## ", 1)[0]


def preamble(text: str) -> str:
    """Everything the brief says before its first heading."""

    return text.split("\n## ", 1)[0]


def settled(chunk: str) -> str:
    """The chunk with every «...» note blanked out.

    A phrase pinned inside one of those is pinned to nothing: the note is a
    question the corpus has not answered, and every word in it goes when
    the answer lands. Blanking them here makes such a pin fail the day it
    is written rather than the day the measurement arrives.
    """

    return _PLACEHOLDER.sub(" ... ", chunk)


def flattened(chunk: str) -> str:
    """A piece of the brief with its emphasis, its backticks and its line
    wrapping taken out, so a phrase can be looked for without caring how
    the paragraph happened to break.

    The markers are deleted rather than spaced out. Markdown puts them
    against the text they mark, so `**Mail**,` spaced out is `mail ,` and
    an editor who drops the bold moves the phrase out from under a pin
    that has nothing to do with emphasis. Deleting them makes the bold and
    the plain spelling flatten alike, which is the whole point of doing
    this before the comparison.
    """

    return " ".join(chunk.replace("*", "").replace("`", "").lower().split())


def unwrapped(chunk: str) -> str:
    """The chunk on one line, its markup left where it is -- for the reads
    that need a backtick to tell them where a value starts."""

    return " ".join(chunk.split())


def insists(where: str, chunk: str, phrases: tuple[str, ...]) -> None:
    """Refuse unless the brief still states the rule this file computes.

    Some of the brief is arithmetic, and no amount of reading turns an
    English sentence into arithmetic: rows are kept when their date is not
    after the boundary because the brief says `on or before`, not because
    anything here can read that phrase and work the comparison out. What
    can be checked is that the sentence has not moved out from under the
    arithmetic.

    That check is not decoration. A brief reworded to say that the window
    excludes its last day, or that a tie goes to the later name, leaves
    this file and the solver both computing the old rule, in perfect
    agreement: every row wrong together, and every row-level comparison
    green. This is the one failure the second derivation cannot catch by
    being a second derivation.
    """

    flat = flattened(settled(chunk))
    missing = [phrase for phrase in phrases if flattened(phrase) not in flat]
    if missing:
        fail(
            f"the brief's {where} no longer says {missing[0]!r}, and this file "
            "hardcodes that rule rather than reading it. The two have gone "
            "apart with nothing else to show it: read the brief again and "
            f"move the derivation to match.\n  brief now: {flat[:280]}"
        )


def backticked(chunk: str) -> list[str]:
    """The backticked spellings in a chunk, in written order, case kept --
    `form_counts` keys are compared character for character."""

    pieces = unwrapped(chunk).split("`")
    if len(pieces) % 2 == 0:
        return fail(f"an unclosed backtick in the brief: {chunk!r}")
    return [piece.strip() for piece in pieces[1::2] if piece.strip()]


def day_names() -> list[str]:
    """The seven weekday names, Monday first, from the calendar rather than
    from a list typed here."""

    opening = datetime.date(2001, 1, 1)
    while opening.weekday() != 0:
        opening += datetime.timedelta(days=1)
    return [
        (opening + datetime.timedelta(days=step)).strftime("%A").lower()
        for step in range(7)
    ]


def month_numbers() -> dict[str, int]:
    """The twelve month names, from the C library and not from here."""

    return {
        datetime.date(2001, number, 1).strftime("%B").lower(): number
        for number in range(1, 13)
    }


# --- values read out of the brief rather than held here ------------------


def table(chunk: str) -> list[list[str]]:
    """The first markdown table in a chunk, header and ruler included.

    Found by its ruler rather than by its outer pipes. Those are optional in
    GFM and cells may be padded to align, so the same table can be written
    several ways and a formatter will choose for you; requiring the outer
    pipes made a legal reformat read as a brief with no form table in it.
    The ruler is the one row markdown itself insists on, so it is the
    landmark: the line above it heads the columns, and the lines below it,
    up to the first without a pipe, are the rows.
    """

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    lines = chunk.splitlines()
    for at, line in enumerate(lines):
        bare = line.strip()
        ruled = bare and "-" in bare and not set(bare) - set("-:| ")
        if not at or not ruled or "|" not in lines[at - 1]:
            continue
        grid = [cells(lines[at - 1]), cells(line)]
        for row in lines[at + 1 :]:
            if "|" not in row:
                break
            grid.append(cells(row))
        return grid
    return []


def term(text: str) -> tuple[str, str]:
    """The two admitted forms, off the brief's own table.

    The `matches` cell has to name the same spelling as the `form` cell: a
    table whose second column admits something the first does not spell is
    a rule this file cannot see, and it would count silently wrong.
    """

    grid = table(section(text, "## What counts as a hit"))
    if len(grid) < 3:
        return fail("the brief's form table has no header, no ruler or no rows")
    header, ruler, *listed = grid
    if [cell.lower() for cell in header] != ["form", "matches"]:
        return fail(
            f"the brief's form table heads its columns {header}, and this file "
            "reads a form column and a matches column"
        )
    if set("".join(ruler)) - set("-: "):
        return fail("the brief's form table has no ruler under its header")
    if len(listed) != 2:
        return fail(
            f"the brief's table admits {len(listed)} form(s). The term is one "
            "word in two, and every count here is built from exactly two."
        )
    forms = []
    for row in listed:
        if len(row) != 2:
            return fail(f"a row of the brief's form table is not two cells: {row}")
        spelled = backticked(row[0])
        if len(spelled) != 1:
            return fail(f"the brief's table names {spelled} in one form cell")
        if flattened(row[1]) != flattened(f"the word *{spelled[0]}*"):
            return fail(
                f"the brief's table says {spelled[0]!r} matches {row[1]!r}, and "
                "this file matches nothing but the word itself"
            )
        forms.append(spelled[0])
    if forms[0] == forms[1]:
        return fail(f"the brief's table spells both of its forms {forms[0]!r}")
    return forms[0], forms[1]


def precedence(text: str, forms: tuple[str, str]) -> None:
    """Which form a message carrying both is counted under.

    `_named_form` returns the first of `forms`, which is the table's first
    row. The brief names that form outright, so it is read and compared
    rather than assumed: a brief that flips the two leaves both
    derivations counting the old way.
    """

    chunk = unwrapped(section(text, "## What counts as a hit"))
    at = chunk.lower().find(BOTH_FORMS)
    if at < 0:
        fail(
            f"the brief no longer says {BOTH_FORMS!r}, and this file counts a "
            f"message carrying both forms once, under {forms[0]!r}"
        )
        return
    named = backticked(chunk[at + len(BOTH_FORMS) :])
    if not named:
        fail("the brief no longer spells which form a both-forms message counts under")
    elif named[0] != forms[0]:
        fail(
            f"the brief counts a message carrying both forms under {named[0]!r}; "
            f"this file counts it under {forms[0]!r}, the first row of the "
            "table. One of the two moved and nothing else would say so."
        )


def fields(text: str) -> None:
    """The deliverable's field names, off the brief's own bullets."""

    chunk = section(text, "## What to produce")
    bullets = _BULLET.findall(chunk)
    top = tuple(name for indent, name in bullets if not indent)
    row = tuple(name for indent, name in bullets if indent)
    if top != TOP_FIELDS:
        fail(
            f"the brief asks for {list(top)} at the top level and this file "
            f"checks {list(TOP_FIELDS)}"
        )
    if row != ROW_FIELDS:
        fail(
            f"the brief's rows carry {list(row)} and this file checks "
            f"{list(ROW_FIELDS)}"
        )


def stated_boundary(text: str, last_day: datetime.date) -> None:
    """The boundary, parsed back out of the sentence it was copied from.

    A window off by one day makes every row wrong together while every
    row-level comparison stays green, and both derivations hold the
    boundary as a number that nothing reads. So the sentence is read: the
    weekday the brief names must be the weekday that date actually falls
    on, and the date must be the one this file windows on.
    """

    chunk = unwrapped(section(text, "## The window"))
    at = chunk.lower().find(BOUNDARY)
    if at < 0:
        fail(f"the brief's window section no longer says {BOUNDARY!r}")
        return
    # The date sits in the clause that follows; the rest of the section
    # carries other numbers -- a working-day count, a message count -- and
    # is no place to go looking for one.
    words = [
        word.strip("*`,.;:()[]—") for word in chunk[at + len(BOUNDARY) :].split()[:14]
    ]
    named = day_names()
    months = month_numbers()
    weekday = next((word for word in words if word.lower() in named), None)
    stated = None
    for word in words:
        if len(word) == 10 and word[4] == "-" and word[7] == "-":
            try:
                stated = datetime.date.fromisoformat(word)
            except ValueError:
                continue
            break
    if stated is None:
        month = day = year = None
        for word in words:
            if word.lower() in months and month is None:
                month = months[word.lower()]
            elif word.isdigit() and len(word) == 4 and year is None:
                year = int(word)
            elif word.isdigit() and len(word) <= 2 and day is None:
                day = int(word)
        if month and day and year:
            try:
                stated = datetime.date(year, month, day)
            except ValueError:
                stated = None
    if stated is None:
        fail(
            "the brief's boundary sentence names no date this file can read. "
            "It has to name one -- a weekday and a date, 'Friday 16 January "
            f"2026' -- because {last_day} is a literal here and nothing else "
            f"checks the two against each other.\n  brief now: {chunk[at : at + 160]}"
        )
    elif weekday is None:
        fail(
            f"the brief closes its window on {stated} and names no weekday. "
            "The weekday is what makes a boundary off by one visible to a "
            "reader; without it the date is unchecked on both sides."
        )
    elif named[stated.weekday()] != weekday.lower():
        fail(
            f"the brief calls {stated} a {weekday}, and it is a "
            f"{named[stated.weekday()].title()}. One of the two is the day the "
            "author meant and the register is built on the other."
        )
    elif stated != last_day:
        fail(
            f"the brief closes its window on {stated} and this file windows on "
            f"{last_day}. Every row is wrong together and every row-level "
            "comparison stays green."
        )


def enumerated(text: str) -> list[str]:
    """The department names the brief enumerates after its roster marker.

    Read line by line, not out of one unwrapped run. The brief asks for the
    names one per line, and the natural markdown for that is a bullet list;
    splitting an unwrapped section on the next `- ` therefore truncated the
    enumeration at its own first entry and read the roster as empty. So the
    lines are taken from the marker until the next *top-level* bullet, which
    is the following field, and each line's backticked name is kept.
    """

    chunk = section(text, "## What to produce")
    at = _ROSTER_AT.search(chunk)
    if at is None:
        return []
    region: list[str] = []
    for line in chunk[at.end() :].splitlines()[1:]:
        marker = _BULLET.match(line)
        if marker and not marker.group(1):
            break
        region.append(line)
    # Backticks are read over the joined region, not line by line: a name
    # is a code span and a code span may wrap, so reading each line alone
    # would call a wrapped name an unclosed backtick and refuse a brief
    # that says exactly what it should.
    return backticked("\n".join(region))


def stated_roster(text: str, departments: tuple[str, ...]) -> None:
    """The department keys the brief enumerates, against the ones held here.

    Both directions, and neither is the one that matters most. A name held
    here and absent from the brief is a key the answer invents; a name the
    brief enumerates and this file does not hold is the roster short by one
    -- the failure the brief's own note about an opposing firm, a court or a
    vendor is warning about, and the one this check used to wave through.
    It only ever asked whether each held name appeared somewhere in the
    brief's text, so a brief listing eight departments against a file
    holding seven passed, and `solve.py` transcribes the same roster by
    hand: two files short by the same one agree, and the missing key's rows
    vanish from the object while every other key still reads right.

    Reading the brief still cannot settle it on its own, because the brief
    is a transcription too. `roster_recorded()` puts the same question to
    the directory, which is the thing the sentence actually points at.
    """

    if not _ROSTER_AT.search(section(text, "## What to produce")):
        fail(f"the brief no longer says {ROSTER!r} before its department keys")
        return
    listed = enumerated(text)
    if not listed:
        fail(
            "the brief enumerates no department keys after "
            f"{ROSTER!r}, and this file holds {list(departments)}"
        )
        return
    absent = [name for name in departments if name not in listed]
    unheld = [name for name in listed if name not in departments]
    if absent or unheld:
        fail(
            f"the brief enumerates {listed} and this file holds "
            f"{list(departments)}"
            + (f"; not in the brief: {absent}" if absent else "")
            + (f"; not held here: {unheld}" if unheld else "")
            + ". A key on one side and not the other is a column of the "
            "answer that nothing else checks."
        )


def roster_recorded(
    directory: sqlite3.Connection, departments: tuple[str, ...]
) -> str | None:
    """The roster against the directory that the brief points at.

    "One key per department **the directory records**" names a source, and
    that source is neither of the two hand transcriptions that compute the
    answer. Every other roster check compares one transcription with
    another, so a department the directory records and both files missed is
    invisible to all of them -- and invisible to the derivation below too,
    unless a row happens to land in it. A department with no rows in the
    window is exactly the case that hides: it owes the object a zero, the
    zero is absent, and every key that is there still reads right.
    """

    recorded = {
        department
        for (department,) in directory.execute("SELECT DISTINCT department FROM people")
    }
    if recorded == set(departments):
        return None
    missing = sorted(recorded - set(departments))
    invented = sorted(set(departments) - recorded)
    return (
        f"roster: the directory records {sorted(recorded)} and this file holds "
        f"{list(departments)}"
        + (f"; missing a key for {missing}" if missing else "")
        + (
            f"; holds a key the directory does not record: {invented}"
            if invented
            else ""
        )
    )


def hardcoded(text: str) -> None:
    """The rest of what this file decides in Python because prose cannot be
    executed, each paired with the sentence it was read off.

    Which side of the boundary a message falls on and by whose clock, what
    `messages_read` counts, what is in scope, what makes a hit and where a
    word begins and ends, how many rows one message makes, what each figure
    counts, how the register is ordered, how the tie breaks, and what goes
    in every column. Each is arithmetic here *and* arithmetic in the
    solver, so the two agree no matter what the brief says.
    """

    insists(
        "account of the term",
        preamble(text),
        (
            "**one word in two admitted forms**",
            "no stem, no wildcard, no synonym, no other ending",
        ),
    )
    insists(
        "window",
        section(text, "## The window"),
        (
            "Report only messages sent **on or before",
            "A message sent after that makes no row here",
            "decided by its date in the firm's own time zone (New York)",
            "the same date this register reports as `sent_date`",
            "not by UTC and not by any other clock a tool prints",
            "`messages_read` counts the messages **inside the window**",
            "There is no need to open anything sent later",
        ),
    )
    insists(
        "account of what is in scope",
        section(text, "## What is in scope"),
        (
            "**Mail**, and the workspace's **channels**",
            "One-to-one direct conversations",
            "leave them out of the register and out of `messages_read`",
        ),
    )
    insists(
        "account of what counts as a hit",
        section(text, "## What counts as a hit"),
        (
            "its body carries either of these two forms",
            "matched case-insensitively",
            "anywhere in the text",
            "**The test is textual, not editorial.**",
            "Do not weigh up whether the message is about the thing the term "
            "was written to find",
            "Letters, digits and the underscore continue a word; every other "
            "character ends one",
            "a hyphenated compound is two words and the form inside it counts",
            "a longer word that merely contains the letters does not",
            "inside a longer *phrase* is a hit; inside a longer *word* is not",
            "**No other ending counts.**",
            "**No synonym counts.**",
            "**One row per message**, however many times either form appears in it",
        ),
    )
    insists(
        "output section",
        section(text, "## What to produce"),
        (
            # `set(truth) != set(TOP_FIELDS)` admits no field the brief
            # does not ask for; `fields()` pins the names and their order
            # but not that the list is closed.
            "with exactly these fields",
            "Every figure is a count of **messages**, never of occurrences",
            "how many messages you examined, mail and channel chat together",
            "how many rows are in `hits`",
            "how many different people wrote one",
            "an object with **both** forms as keys",
            "each spelled character for character as the table above spells it",
            # The department object's "how many rows" was pinned and the
            # form object's was not, though both are counted the same way.
            "each mapped to how many rows carry it",
            "Both keys appear every time, including one at zero",
            "an object with **one key per department the directory records**",
            "each mapped to how many rows were written by people in it",
            "Every key appears every time, including the ones at zero",
            "the person on the most rows",
            "the full name, never an id",
            "Break a tie alphabetically by full name, earlier first",
            "sorted by `ref`, compared as text, ascending",
            "**Mail** uses an id like",
            "addresses a message by its timestamp",
            "Use that, unchanged, every digit",
            "the full name of whoever wrote the message",
            "the date it was written, `YYYY-MM-DD`, in the firm's own time "
            "zone (New York)",
            "for a **mail** message, its subject line exactly as the message "
            "carries it",
            "For a **chat** message, the channel's name",
            "Resolve each through the directory",
            "the department each person belongs to; everyone it lists has one, "
            "people outside the firm included",
            "`department_counts` uses whatever it records for that person",
        ),
    )
    insists(
        "warning about completeness",
        section(text, "## A warning about completeness"),
        (
            "having read the body of every message in the window",
            "not its subject or its snippet",
        ),
    )


# --- the derivation ------------------------------------------------------


def _unmeasured(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if "«MEASURE" in line]


def _unbuilt(forms: tuple[str, str]) -> str | None:
    if any("«" in form for form in forms):
        return "the word family"
    if not DEPARTMENTS:
        return "DEPARTMENTS"
    return None


def _forms_in(body: str, forms: tuple[str, str]) -> set[str]:
    tokens = {token.casefold() for token in _SPLIT.split(body) if token}
    return {form for form in forms if form.casefold() in tokens}


def _named_form(body: str, forms: tuple[str, str]) -> str | None:
    """A message carrying both forms counts once, under the first form the
    brief's table lists -- which `precedence()` checks is the form the
    brief names for it."""

    present = _forms_in(body, forms)
    for form in forms:
        if form in present:
            return form
    return None


def _fail(problems: list[str]) -> int:
    for problem in problems:
        print(f"  MISMATCH  {problem}")
    print(f"\n{len(problems)} disagreement(s) between instruction.md and the oracle.")
    return 1


def main() -> int:
    text = brief_text()
    forms = term(text)
    fields(text)
    precedence(text, forms)
    hardcoded(text)

    if pending := _unmeasured(text):
        raise SystemExit(
            f"off-sense-register: the brief still holds {len(pending)} "
            "unmeasured value(s), so it states no window and no roster to "
            "check yet:\n  - " + "\n  - ".join(pending[:6])
        )
    if (missing := _unbuilt(forms)) is not None:
        raise SystemExit(
            f"off-sense-register: {missing} is still a placeholder. Transcribe "
            "it from instruction.md once the family and the window are "
            "measured -- and read it off the instruction, not off solve.py."
        )
    last_day = datetime.date.fromisoformat(transcribed_last_day())
    stated_boundary(text, last_day)
    stated_roster(text, DEPARTMENTS)

    if not _STATE_ENV or not STATE.is_dir():
        raise SystemExit("set WORKBENCH_STATE to the built bundle's state directory")
    if not ORACLE.is_file():
        raise SystemExit(f"no oracle at {ORACLE} -- run build_tasks.py first")

    truth = json.loads(ORACLE.read_text())
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    slack = sqlite3.connect(f"file:{STATE / 'slack.db'}?mode=ro", uri=True)
    imanage = sqlite3.connect(f"file:{STATE / 'imanage.db'}?mode=ro", uri=True)

    zone = ZoneInfo(FIRM_TZ)
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )

    def sent_on(seconds: int) -> datetime.date:
        return (epoch + datetime.timedelta(seconds=seconds)).astimezone(zone).date()

    # The directory as the agent is served it: iManage calls the field
    # `location`, and it is the only surface that carries it.
    department_of = {
        name: department
        for name, department in imanage.execute("SELECT name, department FROM people")
    }
    name_of = dict(gmail.execute("SELECT person_id, name FROM people"))
    channels = dict(
        slack.execute(
            "SELECT conversation_id, name FROM conversations WHERE kind = 'channel'"
        )
    )

    rows: list[dict] = []
    named: list[str] = []
    read = 0
    for message_id, sender, when, subject, body in gmail.execute(
        "SELECT message_id, sender, time, subject, body FROM messages"
    ):
        if sent_on(when) > last_day:
            continue
        read += 1
        if (form := _named_form(body, forms)) is None:
            continue
        rows.append(
            {
                "ref": message_id,
                "author": name_of[sender],
                "sent_date": sent_on(when).isoformat(),
                "where": subject,
            }
        )
        named.append(form)
    for conversation, sender, when, ts, body in slack.execute(
        "SELECT conversation_id, sender, time, ts, body FROM messages"
    ):
        if conversation not in channels or sent_on(when) > last_day:
            continue
        read += 1
        if (form := _named_form(body, forms)) is None:
            continue
        rows.append(
            {
                "ref": ts,
                "author": name_of[sender],
                "sent_date": sent_on(when).isoformat(),
                "where": channels[conversation],
            }
        )
        named.append(form)

    order = sorted(range(len(rows)), key=lambda i: rows[i]["ref"])
    rows = [rows[i] for i in order]
    named = [named[i] for i in order]

    by_author = Counter(row["author"] for row in rows)
    by_form = dict.fromkeys(forms, 0) | Counter(named)
    by_department = dict.fromkeys(DEPARTMENTS, 0)
    # Reported, never raised. A roster short by one, and a name that does not
    # join between the mail directory and iManage, are the two defects this
    # second route exists to catch; indexing straight into either dict raises
    # KeyError, which aborts before a single check() runs and prints a
    # traceback where the finding belongs.
    roster: list[str] = []
    if (stale := roster_recorded(imanage, DEPARTMENTS)) is not None:
        roster.append(stale)
    for row in rows:
        department = department_of.get(row["author"])
        if department is None:
            roster.append(
                f"directory join: iManage has no row for author "
                f"{row['author']!r}, so its department is uncountable"
            )
        elif department not in by_department:
            roster.append(
                f"roster: {department!r} is recorded on {row['author']} and "
                "missing from DEPARTMENTS -- its rows vanish from the object "
                "while every other key still reads right"
            )
        else:
            by_department[department] += 1
    # Highest count, then the earliest name among those tied.
    best = max(by_author.values(), default=None)
    top_author = min((n for n, c in by_author.items() if c == best), default=None)

    problems: list[str] = sorted(set(roster))

    def check(field: str, mine) -> None:
        if truth.get(field) != mine:
            problems.append(f"{field}: oracle {truth.get(field)!r} != derived {mine!r}")

    if set(truth) != set(TOP_FIELDS):
        problems.append(
            f"top-level fields: oracle {sorted(truth)} != instruction "
            f"{sorted(TOP_FIELDS)}"
        )
    check("messages_read", read)
    check("hits_total", len(rows))
    check("distinct_authors", len(by_author))
    check("form_counts", dict(sorted(by_form.items())))
    check("department_counts", dict(sorted(by_department.items())))
    check("top_author", top_author)
    check("hits", rows)

    # Floors no per-row criterion can see.
    if len(rows) < ROW_FLOOR:
        problems.append(f"row floor: {len(rows)} rows, fewer than {ROW_FLOOR}")
    keyed = {row["ref"] for row in rows}
    if len(keyed) != len(rows):
        problems.append(
            f"key collapse: {len(rows)} rows key to {len(keyed)} refs -- the "
            "ceiling is below 1.0 and row F1 will not show it"
        )
    for field in ROW_FIELDS:
        distinct = {row[field] for row in rows}
        if len(distinct) < 2 and rows:
            problems.append(
                f"constant field: every row has {field}={distinct.pop()!r}, so "
                "an agent that never looks scores full marks on it"
            )
    if set(by_form.values()) == {0}:
        problems.append("both forms are dead in this window")
    if min(by_form.values()) == 0:
        print(
            "  note: one spelling has no rows in this window. The zero key is "
            "required, but a family whose minority form is silent was the "
            "hygiene failure measure_candidates.py exists to print."
        )

    if problems:
        return _fail(problems)
    print(
        f"verify: {len(rows)} rows over {read} messages agree with the oracle, "
        "derived from instruction.md by a second route."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

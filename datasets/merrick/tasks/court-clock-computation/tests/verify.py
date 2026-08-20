r"""An independent derivation of the court-clock register.

    WORKBENCH_STATE=out/merrick/bundle/state python3 tests/verify.py

Every rule below is transcribed from `instruction.md` — the prose the agent
is graded against — and nothing from `solution/solve.py`. Copying the
solver's expression of a rule reproduces its bug and then certifies that
the two agree; two published scores in this tree were the answer key rather
than a measurement, certified exactly that way. The solver finds its three
interval forms with compiled regexes. There is not one regex in this file.

Where more than one computation is defensible, this takes the route the
solver did not. Each line below names the rule, the route a
regex-and-`timedelta` reading naturally takes, and the route taken here:

* **An interval form.** Not one compiled alternation searched over the
  body: the body is cut into words, and each of the three forms is read as
  a small grammar over that word list.
* **A date form.** Not every match of a date alternation collected and then
  sorted by start and by length: a hand-written character reader, tried
  anchored at each word start. The first index that yields anything wins,
  and the longest read at that index is the one taken.
* **A form naming no real day.** Not filtered out after the match: the
  reader's own `date()` refuses it, and the scan carries on to the next
  index by itself.
* **Adding `N` days.** Not one `timedelta(days=N)`: `N` single-day steps
  along the proleptic ordinal.
* **The weekend move.** Not a `{Saturday: +2, Sunday: +1}` offset table:
  one-day steps while the day's *name* is Saturday or Sunday.
* **The window.** Not a bound in seconds from the epoch: the date read back
  out of `instruction.md`'s own sentence, by this file's date reader.
* **The date a message was sent.** Not `epoch + timedelta(seconds=t)`: the
  epoch's own date, walked forward `t // 86_400` days. The two agree while
  the epoch is midnight and diverge once it is not, so `_derive()` says so
  when it is not.
* **The busiest author.** Not one sort on a negated count: the largest
  count, then the earliest name among those tied for it.

The window matters most. It is the one assumption the generator and the
solver both rest on, and their agreement is not evidence: shift the
boundary and every row moves together while every row-level check stays
green. So it is read out of the prose, and never out of a constant here.

## What is deliberately not invented

Three things this file cannot know until the corpus has been counted are
`measure()` calls, and it will not import until they are answered: which
spelled-out numbers the traffic writes, which date shapes it writes, and
whether it abbreviates month names. A plausible default for any of the
three is this repo's most expensive defect. The window is the fourth, and
it is not a `measure()` here only because the instruction states it — where
it is still a placeholder, and where this file refuses to read the example
date inside the placeholder's own text rather than guess past it.

## What is necessarily shared, and therefore proves nothing

The *rule* — three forms, a date-form table, the first date form as the
trigger, day zero, the weekend move. An independence check cannot catch a
rule that disagrees with its own prose, because the prose is what both
derivations read. That is a different gate: `_prose_examples()` below
asserts this transcription admits every phrase `instruction.md` gives as a
form and refuses every phrase it gives as a near miss.

The identifiers are shared too, and deliberately. `ref` is read off the
served surface — `messages.message_id` in gmail, `messages.ts` in slack —
rather than rebuilt from the world log, because an answer key whose rows
name ids the agent's tools never emit is unanswerable. Re-deriving Slack's
`ts` convention here would only mean both derivations move together when
the projection changes and neither notices. `_projection_complete()` goes
the other way instead: it counts the messages the *world log* recorded and
fails if the served surfaces are short of them.

## Three known divergences, left in on purpose

A hyphen does not end a word here, because it must not: *"a 30-day
extension"* is refused by the instruction, and a scan that split on the
hyphen would manufacture the adjacency `30 day` and admit rows nobody
wrote. The cost runs the other way — a body written *"within 10
days-of-service"* is refused here and would be admitted by a `\b`-anchored
regex. Likewise a two-digit year (`3/14/26`) is not among the shapes the
instruction screens, so it reads as no date form at all rather than as
`3/14`. Third, what stands between the number and `days` is read as
words rather than as whitespace, so *"within 10 **business** days"* is one
form here and is refused by a `\s+`-joined pattern. No body writes that
today; the corpus is still recording, and a disagreement of any of the
three kinds is adjudicated against `instruction.md`, never by patching
whichever side is easier to change.
"""

import calendar
import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3]))

from pending import measure  # noqa: E402

TASK = _HERE.parents[1]
ORACLE = _HERE.parent / "oracle.json"
INSTRUCTION = TASK / "instruction.md"

# ---------------------------------------------------------------------------
# What the corpus has to supply
#
# Read each off `instruction.md` once its own «MEASURE» has been counted
# against the traffic. Not off `solve.py`, and not off a guess: a list
# naming a word the firm never writes admits nothing, while a list missing
# one it writes often scores every instance as a hallucination.

SPELLED_NUMBERS: dict[str, int] = measure(
    "the spelled-out numbers instruction.md admits where `N` goes -- the "
    "ones this corpus writes inside one of the three forms -- lowercased "
    'and mapped to their integer value, e.g. {"ten": 10}'
)

# The date shapes implemented below, by name:
#   month-first   March 14 / March 14th / March 14, 2026
#   day-first     14 March / 14th March / 14 March 2026
#   slash         3/14 / 3/14/2026
#   iso           2026-03-14
SHAPES = ("month-first", "day-first", "slash", "iso")

CORPUS_SHAPES: tuple[str, ...] = measure(
    "which of the names in SHAPES instruction.md's finished date-form table "
    "actually lists, as a tuple. A shape the firm never writes costs nothing "
    "to leave out; one it writes often and this omits turns every such "
    "message into a wrong trigger. `slash` carries a hazard the others do "
    'not -- "1/2 day" reads as 2 January -- so leave it out unless the '
    "corpus really writes slash dates"
)

CORPUS_MONTH_ABBREVIATIONS: bool = measure(
    "whether that table admits abbreviated month names (`Mar`, `Sept`). The "
    "instruction counts them separately from the full spellings, so this is "
    "its own answer: True or False"
)

# ---------------------------------------------------------------------------
# The deliverable's shape, from "What to produce". Agreeing with the solver
# about the schema is fine; the schema is not the rule.

TOP_FIELDS = frozenset(
    {
        "messages_read",
        "deadlines_total",
        "distinct_authors",
        "rolled_count",
        "form_counts",
        "busiest_author",
        "deadlines",
    }
)
ROW_FIELDS = frozenset(
    {
        "ref",
        "author",
        "sent_date",
        "interval_days",
        "raw_due_date",
        "due_date",
        "rolled",
    }
)
# The order the instruction's table lists them in, which is the order that
# settles a body naming two forms for the same number.
FORM_ORDER = ("within N days", "N days after", "due in N days")
# Graded per row, from tests/criteria.py. `ref` and `interval_days` are the
# key rather than graded fields, which is why they are not here.
GRADED = ("author", "sent_date", "raw_due_date", "due_date", "rolled")
# "the shortest window ... that clears the twelve-row floor, with both
# values of `rolled` present and rows written by more than one author"
# -- instruction.md, "The window".
ROW_FLOOR = 12


# ---------------------------------------------------------------------------
# The rule: what names an interval
#
# "Exactly these three forms, matched case-insensitively, anywhere in a
# message body": `within N days`, `N days after`, `due in N days`. Between
# the number and `days` the register accepts nothing at all, `business`, or
# `calendar`; `day` and `days` read alike.

_UNITS = frozenset({"business", "calendar"})
_DAY = frozenset({"day", "days"})
# What stays *inside* a word. The hyphen is here because the instruction
# refuses "a 30-day extension": splitting on it would invent the adjacency
# the register is supposed to refuse.
_JOINERS = "-'’"


def _words(body: str) -> list[str]:
    """The body as lowercased words: runs of letters and digits, keeping a
    hyphen or apostrophe that sits between two of them.

    So `30-day` is one word and names nothing, `days'` sheds its trailing
    apostrophe and reads as `days`, and `days—the` is two words.
    """

    out: list[str] = []
    current: list[str] = []
    for character in body:
        if character.isalnum():
            current.append(character.lower())
        elif character in _JOINERS and current:
            current.append(character)
        elif current:
            out.append("".join(current).rstrip(_JOINERS))
            current = []
    if current:
        out.append("".join(current).rstrip(_JOINERS))
    return [word for word in out if word]


def _number(word: str) -> int | None:
    """ "`N` is written either in digits or as one of these words, and no
    others" -- anything else standing where `N` goes is not a form."""

    if word.isdigit():
        return int(word)
    return SPELLED_NUMBERS.get(word)


def _counts_days(words: list[str], at: int) -> tuple[int | None, int]:
    """If `words[at:]` opens with `<N> [business|calendar] day(s)`: that
    number, and the index just past the day word. Otherwise `(None, at)`."""

    if at >= len(words):
        return None, at
    value = _number(words[at])
    if value is None:
        return None, at
    after = at + 1
    if after < len(words) and words[after] in _UNITS:
        after += 1
    if after < len(words) and words[after] in _DAY:
        return value, after + 1
    return None, at


def _intervals(body: str) -> dict[int, str]:
    """Every distinct number of days the body names, mapped to the form that
    named it -- the first of the three in the table's order.

    "A message makes one row for each distinct number of days its forms
    name", so the number is the key and a repeat is not a second row.
    """

    words = _words(body)
    found: dict[int, str] = {}

    def keep(value: int | None, form: str) -> None:
        if value is None:
            return
        already = found.get(value)
        if already is None or FORM_ORDER.index(form) < FORM_ORDER.index(already):
            found[value] = form

    for index, word in enumerate(words):
        if word == "within":
            keep(_counts_days(words, index + 1)[0], "within N days")
        value, after = _counts_days(words, index)
        if value is not None and after < len(words) and words[after] == "after":
            keep(value, "N days after")
        if word == "due" and index + 1 < len(words) and words[index + 1] == "in":
            keep(_counts_days(words, index + 2)[0], "due in N days")
    return found


# ---------------------------------------------------------------------------
# The rule: what the interval counts from
#
# "The trigger is the first date form in the body, reading left to right:
# the one that starts earliest", and the longer where two start together.
# Read one character at a time rather than by collecting matches: each shape
# is a reader that either consumes text starting exactly at an index, or
# does not.

_ORDINALS = ("st", "nd", "rd", "th")


def _months(abbreviated: bool) -> dict[str, int]:
    """Month spellings, from the standard library's own tables rather than
    typed out a second time here."""

    table = {
        name.lower(): number for number, name in enumerate(calendar.month_name) if name
    }
    if abbreviated:
        for number, name in enumerate(calendar.month_abbr):
            if name:
                table[name.lower()] = number
        # The instruction names `Sept` explicitly and `calendar` does not.
        table["sept"] = 9
    return table


def _digits(text: str, at: int) -> tuple[str | None, int]:
    end = at
    while end < len(text) and text[end].isdigit():
        end += 1
    return (text[at:end] if end > at else None), end


def _letters(text: str, at: int) -> tuple[str | None, int]:
    end = at
    while end < len(text) and text[end].isalpha():
        end += 1
    return (text[at:end] if end > at else None), end


def _blank(text: str, at: int) -> int | None:
    """Past a run of whitespace, or None when there is none to pass."""

    end = at
    while end < len(text) and text[end].isspace():
        end += 1
    return end if end > at else None


def _ordinal(text: str, at: int) -> int:
    """Past `st`/`nd`/`rd`/`th` when that is the whole of the next word."""

    word, end = _letters(text, at)
    if word is not None and word.lower() in _ORDINALS:
        return end
    return at


def _month_first(text: str, at: int, months: dict[str, int]):
    word, cursor = _letters(text, at)
    month = months.get(word.lower()) if word else None
    if month is None:
        return None
    spaced = _blank(text, cursor)
    if spaced is None:
        return None
    day, cursor = _digits(text, spaced)
    if day is None or len(day) > 2:
        return None
    cursor = _ordinal(text, cursor)
    year = None
    if text.startswith(",", cursor):
        spaced = _blank(text, cursor + 1)
        if spaced is not None:
            written, end = _digits(text, spaced)
            if written is not None and len(written) == 4:
                year, cursor = int(written), end
    return year, month, int(day), cursor


def _day_first(text: str, at: int, months: dict[str, int]):
    day, cursor = _digits(text, at)
    if day is None or len(day) > 2:
        return None
    cursor = _ordinal(text, cursor)
    spaced = _blank(text, cursor)
    if spaced is None:
        return None
    word, cursor = _letters(text, spaced)
    month = months.get(word.lower()) if word else None
    if month is None:
        return None
    year = None
    spaced = _blank(text, cursor)
    if spaced is not None:
        written, end = _digits(text, spaced)
        if written is not None and len(written) == 4:
            year, cursor = int(written), end
    return year, month, int(day), cursor


def _slash(text: str, at: int, months: dict[str, int]):
    month, cursor = _digits(text, at)
    if month is None or len(month) > 2 or not text.startswith("/", cursor):
        return None
    day, cursor = _digits(text, cursor + 1)
    if day is None or len(day) > 2:
        return None
    year = None
    if text.startswith("/", cursor):
        written, end = _digits(text, cursor + 1)
        if written is None or len(written) != 4:
            # Not a shape the instruction screens. Refused whole, rather
            # than clipped back to the part before the second slash.
            return None
        year, cursor = int(written), end
    return year, int(month), int(day), cursor


def _iso(text: str, at: int, months: dict[str, int]):
    year, cursor = _digits(text, at)
    if year is None or len(year) != 4 or not text.startswith("-", cursor):
        return None
    month, cursor = _digits(text, cursor + 1)
    if month is None or len(month) != 2 or not text.startswith("-", cursor):
        return None
    day, cursor = _digits(text, cursor + 1)
    if day is None or len(day) != 2:
        return None
    return int(year), int(month), int(day), cursor


_READERS = {
    "month-first": _month_first,
    "day-first": _day_first,
    "slash": _slash,
    "iso": _iso,
}


def _date_at(
    text: str,
    at: int,
    shapes: tuple[str, ...],
    months: dict[str, int],
    fallback_year: int | None,
) -> datetime.date | None:
    """The longest real date starting exactly at `at`, or None.

    "Where two forms start at the same place ... take the longer one." A
    shape naming no real day is not a date form, so it drops out here and a
    shorter one at the same index may still stand.
    """

    best: tuple[int, datetime.date] | None = None
    for shape in shapes:
        read = _READERS[shape](text, at, months)
        if read is None:
            continue
        year, month, day, end = read
        if end < len(text) and text[end].isalnum():
            # The form runs on into a longer word, so it is not that form.
            continue
        if year is None:
            # "When a date form names no year, the year is the year the
            # message was sent." Where there is no such year to fall back
            # on -- the window sentence -- the shape does not apply.
            if fallback_year is None:
                continue
            year = fallback_year
        try:
            found = datetime.date(year, month, day)
        except ValueError:
            continue
        if best is None or end > best[0]:
            best = (end, found)
    return None if best is None else best[1]


def _first_date(
    text: str,
    shapes: tuple[str, ...],
    months: dict[str, int],
    fallback_year: int | None,
    start: int = 0,
    stop: int | None = None,
) -> datetime.date | None:
    """The first date form by where it starts.

    Only word-start indices are tried. That narrows nothing -- every shape
    opens with a letter or a digit, and none may begin part-way through a
    word -- and it keeps a character-by-character scan over six months of
    bodies from costing minutes.
    """

    last = len(text) if stop is None else min(stop, len(text))
    for index in range(start, last):
        if not text[index].isalnum():
            continue
        if index and text[index - 1].isalnum():
            continue
        found = _date_at(text, index, shapes, months, fallback_year)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# The rule: counting


def _forward(day: datetime.date, steps: int) -> datetime.date:
    """`steps` single days forward. "The trigger day is day zero", so ten
    days from the 14th is the 24th."""

    for _ in range(steps):
        day = datetime.date.fromordinal(day.toordinal() + 1)
    return day


def _weekend_move(raw: datetime.date) -> datetime.date:
    """Saturday to the Monday two days later, Sunday to the Monday one day
    later, anything else where it is.

    Walked a day at a time off the day's *name*, so no weekday-to-offset
    table decides it. "Only Saturday and Sunday move a date": this register
    keeps no holiday calendar, and a deadline on New Year's Day stays there.
    """

    day = raw
    while calendar.day_name[day.weekday()] in ("Saturday", "Sunday"):
        day = _forward(day, 1)
    return day


# ---------------------------------------------------------------------------
# The window, read back out of the prose


def _window_last_day(prose: str) -> datetime.date:
    """The instruction states the boundary "in exactly the shape 'Friday 16
    January 2026'", so it is read back out with this file's own date reader
    -- the weekday word is not a date shape and is skipped, the day-month-
    year that follows is."""

    marker = "on or before"
    at = prose.find(marker)
    if at < 0:
        raise SystemExit(
            f"{INSTRUCTION} never says 'on or before', so the window cannot "
            "be read out of it and nothing derived here is evidence"
        )
    start = at + len(marker)
    span = prose[start : start + 200]
    if "«MEASURE" in span:
        raise SystemExit(
            "the window in instruction.md is still a placeholder:\n"
            f"  ...{span.splitlines()[0].strip()}\n"
            "Its own text carries an example date, and reading that would be "
            "inventing the boundary -- the defect this file exists to refuse. "
            "Measure the window first."
        )
    found = _first_date(prose, SHAPES, _months(True), None, start, start + 200)
    if found is None:
        raise SystemExit(
            "instruction.md names no full date after 'on or before' -- "
            f"expected the shape 'Friday 16 January 2026', saw {span!r}"
        )
    return found


# ---------------------------------------------------------------------------
# Reading the served state


def _open(state: Path, name: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{state / name}?mode=ro", uri=True)


def _epoch_stamp(gmail, slack) -> datetime.datetime:
    """The epoch, as both surfaces state it. They have to agree: a
    `sent_date` that depends on which tool you asked is not a date."""

    stated = {
        surface: dict(handle.execute("SELECT key, value FROM meta"))["epoch"]
        for surface, handle in (("gmail", gmail), ("slack", slack))
    }
    if len(set(stated.values())) != 1:
        raise SystemExit(f"the surfaces disagree about the epoch: {stated}")
    return datetime.datetime.fromisoformat(stated["gmail"])


def _directory(gmail, slack) -> dict[str, str]:
    """Person id to full name -- "`author` is a person's full name, never an
    id". Both surfaces carry the directory, and a disagreement between them
    is a finding rather than something to pick a winner from."""

    names: dict[str, str] = {}
    for handle in (gmail, slack):
        for person, name in handle.execute("SELECT person_id, name FROM people"):
            if names.setdefault(person, name) != name:
                raise SystemExit(f"{person} is named two ways: {names[person]}/{name}")
    return names


def _served(gmail, slack):
    """Every message the two surfaces serve, as (ref, sender, seconds, body).

    `ref` is "how the message's own system names it", read off the surface
    rather than rebuilt, because a row naming an id the tools never emit is
    not answerable.
    """

    mail = "SELECT message_id, body, sender, time FROM messages"
    for ref, body, sender, seconds in gmail.execute(mail):
        yield ref, sender, seconds, body
    chat = "SELECT ts, body, sender, time FROM messages"
    for ref, body, sender, seconds in slack.execute(chat):
        yield ref, sender, seconds, body


def _sent_on(epoch_day: datetime.date, seconds: int) -> datetime.date:
    """Whole days walked forward from the epoch's own date, rather than a
    seconds addition on an aware datetime. The two part company across a
    daylight-saving boundary, and that disagreement is the point."""

    return _forward(epoch_day, int(seconds) // 86_400)


# ---------------------------------------------------------------------------
# The derivation


def _derive(state: Path, last_day: datetime.date) -> dict:
    gmail = _open(state, "gmail.db")
    slack = _open(state, "slack.db")
    epoch = _epoch_stamp(gmail, slack)
    epoch_day = epoch.date()
    # Walking whole days from the epoch's date and adding the seconds to the
    # stamp itself agree exactly while the stamp is midnight, whatever its
    # zone does later in the year -- the offset cancels. They part company
    # only once the epoch carries a time of day, and then for every message
    # whose own time of day pushes it over the next midnight. So the note is
    # on that, not on a daylight-saving boundary neither derivation crosses.
    if (epoch.hour, epoch.minute, epoch.second, epoch.microsecond) != (0, 0, 0, 0):
        print(
            f"  note: the epoch is {epoch.time()}, not midnight, so a "
            "`sent_date` here and one taken by adding seconds to the stamp "
            "disagree for any message late enough in its own day. A row "
            "below may be that rather than a disagreement about the rule."
        )
    names = _directory(gmail, slack)
    months = _months(bool(CORPUS_MONTH_ABBREVIATIONS))

    read = 0
    rows: list[dict] = []
    named: list[str] = []
    for ref, sender, seconds, body in _served(gmail, slack):
        sent = _sent_on(epoch_day, seconds)
        if sent > last_day:
            continue
        read += 1
        # "When the body carries no date form at all, the trigger is the
        # date the message was sent."
        trigger = _first_date(body, CORPUS_SHAPES, months, sent.year) or sent
        for days, form in sorted(_intervals(body).items()):
            raw = _forward(trigger, days)
            due = _weekend_move(raw)
            rows.append(
                {
                    "ref": ref,
                    "author": names[sender],
                    "sent_date": sent.isoformat(),
                    "interval_days": days,
                    "raw_due_date": raw.isoformat(),
                    "due_date": due.isoformat(),
                    "rolled": due != raw,
                }
            )
            named.append(form)

    order = sorted(
        range(len(rows)),
        key=lambda index: (rows[index]["ref"], rows[index]["interval_days"]),
    )
    rows = [rows[index] for index in order]
    named = [named[index] for index in order]

    by_form = dict.fromkeys(FORM_ORDER, 0)
    by_author: dict[str, int] = {}
    for row, form in zip(rows, named, strict=True):
        by_form[form] += 1
        by_author[row["author"]] = by_author.get(row["author"], 0) + 1

    # "the person on the most rows. Break a tie alphabetically, earlier
    # first" -- the most rows, then the earliest name among those tied.
    most = max(by_author.values(), default=None)
    busiest = min((who for who, n in by_author.items() if n == most), default=None)

    return {
        "messages_read": read,
        "deadlines_total": len(rows),
        "distinct_authors": len(by_author),
        "rolled_count": sum(1 for row in rows if row["rolled"]),
        "form_counts": by_form,
        "busiest_author": busiest,
        "deadlines": rows,
    }


# ---------------------------------------------------------------------------
# Gates no comparison with the oracle can make


def _measured() -> None:
    """The three `measure()` answers are hand-written, and only one of them
    fails loudly on its own.

    `CORPUS_SHAPES` naming a shape this file does not implement is caught
    below. `SPELLED_NUMBERS` is not caught anywhere: a key written `Ten`, or
    `twenty one` with the space left in, never equals a token this file's
    own scanner produces, so it admits nothing and every instance the firm
    wrote is scored as a hallucination -- the defect the comment above the
    constants warns about, and the one no example in `_prose_examples()`
    would find, because every example there writes its number in digits.
    """

    if unknown := sorted(set(CORPUS_SHAPES) - set(SHAPES)):
        raise SystemExit(f"CORPUS_SHAPES names no such shape: {unknown}")
    if not isinstance(SPELLED_NUMBERS, dict):
        raise SystemExit(f"SPELLED_NUMBERS is not a mapping: {SPELLED_NUMBERS!r}")
    for word, value in sorted(SPELLED_NUMBERS.items(), key=str):
        if not isinstance(word, str) or _words(word) != [word]:
            raise SystemExit(
                f"SPELLED_NUMBERS key {word!r} is not one lowercase word as "
                "this file cuts words, so no body can ever match it and "
                "every instance of it would score as a hallucination"
            )
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SystemExit(
                f"SPELLED_NUMBERS[{word!r}] is {value!r}; `interval_days` is "
                '"the number the form names, as an integer"'
            )


def _prose_examples() -> list[str]:
    """The transcription admits every phrase instruction.md calls a form and
    refuses every phrase it calls a near miss.

    A pattern narrower or wider than the prose it implements fails here,
    rather than in a rollout where it would read as a model error.
    """

    admitted = (
        ("produce the privilege log within 10 days", "within N days", 10),
        ("objections are due 30 days after service", "N days after", 30),
        ("the opposition brief is due in 14 days", "due in N days", 14),
        ("within 10 days of service", "within N days", 10),
        ("due in 14 days or sooner", "due in N days", 14),
        ("turn this around within 5 days if the vendor helps", "within N days", 5),
        ("the standard clause gives them 30 days after notice", "N days after", 30),
        ("respond within 10 business days", "within N days", 10),
        ("respond within 10 calendar days", "within N days", 10),
        ("file the notice within 1 day", "within N days", 1),
    )
    refused = (
        "produce within 2 weeks",
        "produce within 3 months",
        "we need 30 days' notice",
        "responses are due 30 days before the hearing",
        "I'll have it in 10 days",
        "we agreed a 30-day extension",
        "the 14 day window has closed",
        "produce within a couple of days",
        "produce within the week",
        "the deposition is on 14 March",
    )

    problems = []
    for phrase, form, days in admitted:
        got = _intervals(phrase)
        if got.get(days) != form:
            problems.append(
                f"instruction example not read as {form}/{days}: {phrase!r} -> {got}"
            )
    for phrase in refused:
        got = _intervals(phrase)
        if got:
            problems.append(f"near miss admitted: {phrase!r} -> {got}")

    # Every example above writes its number in digits, so none of them
    # touches SPELLED_NUMBERS at all. Each measured word is put through all
    # three forms here: a spelling the scanner cannot reach is a silent
    # under-count of exactly the instances the measurement was taken for.
    for word, value in sorted(SPELLED_NUMBERS.items()):
        for phrase, form in (
            (f"produce the log within {word} days", "within N days"),
            (f"objections are due {word} days after service", "N days after"),
            (f"the brief is due in {word} calendar days", "due in N days"),
        ):
            got = _intervals(phrase)
            if got.get(value) != form:
                problems.append(
                    f"measured spelling unreachable as {form}/{value}: "
                    f"{phrase!r} -> {got}"
                )
    return problems


def _prose_arithmetic() -> list[str]:
    """The parts of the rule real traffic rarely exercises: one number named
    twice, two numbers in one body, the weekend move, day zero, and the
    trigger tie-breaks. A tie-break that disagrees with the instruction
    survives every sweep and then decides the one row that finally ties."""

    months = _months(True)
    problems = []

    both = _intervals("within 10 days, and in any case due in 10 days")
    if both != {10: "within N days"}:
        problems.append(f"one number named by two forms is one row: {both}")
    two = _intervals("within 10 days; the objection is 30 days after service")
    if sorted(two) != [10, 30]:
        problems.append(f"two numbers are two rows: {two}")
    twice = _intervals("within 10 days -- again, within 10 days")
    if twice != {10: "within N days"}:
        problems.append(f"one form written twice is one row: {twice}")

    # Saturday 14 March 2026 moves to Monday the 16th, Sunday the 15th to
    # the same Monday, Friday the 13th not at all.
    for landing, wanted in (
        (datetime.date(2026, 3, 14), datetime.date(2026, 3, 16)),
        (datetime.date(2026, 3, 15), datetime.date(2026, 3, 16)),
        (datetime.date(2026, 3, 13), datetime.date(2026, 3, 13)),
    ):
        moved = _weekend_move(landing)
        if moved != wanted:
            problems.append(f"weekend move: {landing} -> {moved}, wanted {wanted}")
    # Day zero: `within 10 days` triggered on 14 March falls due on the 24th.
    if _forward(datetime.date(2026, 3, 14), 10) != datetime.date(2026, 3, 24):
        problems.append("the trigger day is day zero, so the count must land on +N")

    sent = datetime.date(2026, 3, 12)
    for text, wanted in (
        # The longer form wins where a shorter shape opens it, and the
        # earlier start wins over the later. The year is deliberately not
        # the sent year: with 2026 here, reading only the `March 14` inside
        # `March 14, 2025` lands on the same date and the case proves
        # nothing.
        ("filed March 14, 2025 and served March 20", datetime.date(2025, 3, 14)),
        # A trigger may be in the past, and is still the first one.
        ("The order issued 3 March; produce within 10 days", datetime.date(2026, 3, 3)),
        # A trigger may have nothing to do with the interval.
        (
            "Following our call of 6 January, the response is due in 14 days",
            datetime.date(2026, 1, 6),
        ),
        # No date form at all: the date the message was sent.
        ("produce within 10 days", sent),
        # No real day: pass over it and take the next one in the body.
        ("February 30 was wrong; read 4 April", datetime.date(2026, 4, 4)),
        # ... and with no next one, the sent date again.
        ("April 31 was wrong", sent),
        # "When it names no month -- it is not a date form."
        ("the January 2026 filings are due in 14 days", sent),
        # Each shape this file implements, and two that are not shapes.
        ("March 14th and nothing else", datetime.date(2026, 3, 14)),
        ("14 March and nothing else", datetime.date(2026, 3, 14)),
        ("14th March 2025 and nothing else", datetime.date(2025, 3, 14)),
        ("3/14 and nothing else", datetime.date(2026, 3, 14)),
        ("3/14/2025 and nothing else", datetime.date(2025, 3, 14)),
        ("2025-03-14 and nothing else", datetime.date(2025, 3, 14)),
        ("Sept 14 and nothing else", datetime.date(2026, 9, 14)),
        ("3/14/26 and nothing else", sent),
        ("March 14x and nothing else", sent),
    ):
        got = _first_date(text, SHAPES, months, sent.year) or sent
        if got != wanted:
            problems.append(f"trigger {text!r}: read {got}, wanted {wanted}")
    return problems


def _floors(mine: dict) -> list[str]:
    """What no per-row criterion can see: too few rows, a dead distinction,
    a graded column carrying one value in every row."""

    rows = mine["deadlines"]
    problems = []
    if len(rows) < ROW_FLOOR:
        problems.append(
            f"row floor: {len(rows)} rows, fewer than the {ROW_FLOOR} the "
            "window is supposed to be chosen to clear"
        )
    if {row["rolled"] for row in rows} != {True, False}:
        problems.append(
            "the weekend move is dead in this window: `rolled` does not carry "
            "both values, so a register that never moved a date scores full "
            "marks on the rule this task is named for"
        )
    if mine["distinct_authors"] < 2:
        problems.append(
            "one author wrote every row, so `distinct_authors` and "
            "`busiest_author` are free marks"
        )
    for field in GRADED:
        values = {row[field] for row in rows}
        if rows and len(values) < 2:
            problems.append(
                f"constant graded field: every row has {field}="
                f"{next(iter(values))!r}, so grading it measures nothing"
            )
    if min(mine["form_counts"].values(), default=0) == 0:
        silent = sorted(f for f, n in mine["form_counts"].items() if n == 0)
        print(f"  note: no rows for {silent} here (the zero key is still required)")
    return problems


def _keys_apart(rows: list[dict], side: str) -> list[str]:
    """(ref, interval_days) must tell every real row apart, on both sides. A
    key that collapses two caps the ceiling below 1.0 for reasons no agent
    can fix, and row F1 reads 1.000 while it happens."""

    keyed = {(row["ref"], row["interval_days"]) for row in rows}
    if len(keyed) != len(rows):
        return [f"{side}: {len(rows)} rows collapse onto {len(keyed)} keys"]
    return []


def _projection_complete(state: Path, last_day: datetime.date, read: int) -> list[str]:
    """The served surfaces carry every in-window message the world recorded.

    Reading `ref` off the projection is what keeps the answer key
    answerable, and it is also what would hide a projection quietly
    dropping messages. So count them in the world log instead. Skipped --
    loudly -- when that log is not on this machine.
    """

    source = state.parent / "SOURCE"
    if not source.is_file():
        print(f"  note: no {source}, so the world-log completeness check is skipped")
        return []
    world = Path(source.read_text().strip())
    if not world.is_file():
        print(f"  note: {world} is gone, so the completeness check is skipped")
        return []

    epoch_day: datetime.date | None = None
    recorded = 0
    with world.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            tag = event.get("tag")
            if tag == "sim.run.started":
                stamp = (event.get("payload") or {})["epoch"]
                epoch_day = datetime.datetime.fromisoformat(stamp).date()
            elif tag in ("email.message", "chat.message"):
                if epoch_day is None:
                    return [f"{world}: a message precedes sim.run.started"]
                if _sent_on(epoch_day, event["time"]) <= last_day:
                    recorded += 1
    if epoch_day is None:
        return [f"{world} carries no sim.run.started, so it names no epoch"]
    if recorded != read:
        return [
            f"the world log records {recorded} in-window messages and the "
            f"surfaces serve {read}: either the register is graded on traffic "
            "the agent's tools cannot reach, or the oracle is short of it"
        ]
    return []


def _compare(mine: dict, oracle: dict) -> list[str]:
    problems = []
    if set(oracle) != TOP_FIELDS:
        problems.append(
            f"top-level fields: oracle {sorted(oracle)}, instruction "
            f"{sorted(TOP_FIELDS)}"
        )
    for field in sorted(TOP_FIELDS - {"deadlines"}):
        if mine.get(field) != oracle.get(field):
            problems.append(
                f"{field}: derived {mine.get(field)!r}, oracle {oracle.get(field)!r}"
            )

    stray = {key for row in oracle.get("deadlines", []) for key in row} ^ ROW_FIELDS
    if stray:
        problems.append(f"row fields the instruction does not name, or misses: {stray}")

    ours = {(row["ref"], row["interval_days"]): row for row in mine["deadlines"]}
    theirs = {(row["ref"], row["interval_days"]): row for row in oracle["deadlines"]}
    for key in sorted(set(ours) - set(theirs), key=str)[:20]:
        problems.append(f"row only in this derivation: {key}")
    for key in sorted(set(theirs) - set(ours), key=str)[:20]:
        problems.append(f"row only in the oracle: {key}")
    for key in sorted(set(ours) & set(theirs), key=str):
        for field in GRADED:
            if ours[key][field] != theirs[key][field]:
                problems.append(
                    f"{key} {field}: derived {ours[key][field]!r}, "
                    f"oracle {theirs[key][field]!r}"
                )

    # "sorted by `ref`, and within one `ref` by `interval_days` ascending"
    if [(r["ref"], r["interval_days"]) for r in oracle["deadlines"]] != [
        (r["ref"], r["interval_days"]) for r in mine["deadlines"]
    ]:
        problems.append("the oracle's rows are not in the instruction's sort order")
    return problems


# ---------------------------------------------------------------------------


def _report(problems: list[str], headline: str) -> int:
    print(f"{len(problems)} {headline}:")
    for problem in problems[:60]:
        print(f"  {problem}")
    if len(problems) > 60:
        print(f"  ... and {len(problems) - 60} more")
    return 1


def main() -> int:
    # The measured values before anything reads them, then the rule against
    # its own prose. A derivation from a rule that disagrees with
    # instruction.md is not evidence about the oracle; it is a second copy
    # of the same mistake.
    _measured()
    if problems := _prose_examples() + _prose_arithmetic():
        return _report(problems, "disagreement(s) with instruction.md's own examples")

    where = os.environ.get("WORKBENCH_STATE")
    if not where:
        raise SystemExit("set WORKBENCH_STATE to the built bundle's state directory")
    state = Path(where)
    if not state.is_dir():
        raise SystemExit(f"no bundle state at {state}")
    if not ORACLE.is_file():
        raise SystemExit(f"no oracle at {ORACLE} -- run build_tasks.py first")

    last_day = _window_last_day(INSTRUCTION.read_text())
    if last_day >= datetime.date(2026, 3, 8):
        print(
            "  note: this window reaches past 8 March 2026, when New York "
            "leaves the epoch's fixed -05:00. Walking whole days from the "
            "epoch's date and converting seconds in the zone can disagree "
            "near midnight from there on -- a row below may be that."
        )

    mine = _derive(state, last_day)
    oracle = json.loads(ORACLE.read_text())

    problems = _keys_apart(mine["deadlines"], "this derivation")
    problems += _keys_apart(oracle["deadlines"], "the oracle")
    problems += _floors(mine)
    problems += _projection_complete(state, last_day, mine["messages_read"])
    problems += _compare(mine, oracle)
    if problems:
        return _report(problems, "disagreement(s) with the oracle")

    print(
        f"verify: {mine['deadlines_total']} rows over {mine['messages_read']} "
        f"messages through {last_day.isoformat()}, {mine['rolled_count']} "
        "rolled, agree with the oracle by a second derivation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

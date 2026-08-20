"""An independent derivation of the same answer.

Every rule below is transcribed from `instruction.md` — the prose the
agent is graded against — and never from `solution/solve.py`. Copying the
solver's expression of a rule reproduces its bug and then certifies that
the two agree; two published scores in this tree were the answer key
rather than a measurement, certified exactly that way.

Where more than one computation is defensible, this uses the one the
solver did not:

* the solver finds forms with seven regular expressions over the raw
  body; this squashes each run of whitespace to one space, lowercases,
  and searches for the literal phrases the instruction's table lists,
  mapping every hit back to its position in the original body. The
  regexes' `\\s+` and this squash agree only if the instruction's forms
  really are fixed word sequences, which is what the table claims.
* the solver resolves a weekday by modular arithmetic; this walks
  forward a day at a time until the name matches.
* the solver takes the end of a month from `calendar.monthrange`; this
  steps to the first of the next month and back one day.
* the solver takes the Friday of a week as `sent + (4 - weekday)`; this
  walks back to that week's Monday and forward four days.

Three things the solver and the brief both rest on are read out of
`instruction.md` here rather than copied into this file by hand, because
a hand-kept copy agrees with whatever it was copied from and drifts in
silence afterwards:

**The window.** The solver bounds the corpus in the world's own seconds;
this reads the weekday-and-date the brief prints and bounds it by the
calendar. Their agreement is the check — a window off by a day makes
every row wrong together while every row-level check stays green — and
the brief's own weekday name is checked against that date, so a brief
that says "Friday 16 January 2026" of a Thursday fails here.

**The numerals admitted after `within`.** A vocabulary the solver knows
and the brief never names is a rule the agent was never told.

**That the brief holds no unmeasured placeholder at all.** An authoring
note left in the brief ships to the agent as prose, and this one names
the row floors and the solver.

    WORKBENCH_STATE=out/merrick/bundle/state python3 tests/verify.py
"""

import datetime
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# Written-out counts the instruction admits inside `within N days`. Kept
# here rather than imported from the solver: sharing the table would
# share any omission in it, and an omission is exactly the kind of bug a
# second derivation exists to catch.
_NUMBERS: dict[str, int] = {
    "a": 1,
    "two": 2,
    "three": 3,
    "five": 5,
    "ten": 10,
}

# The window's last day, as `instruction.md` states it. Deliberately
# unmeasured: the world is still recording, and a plausible date written
# here is indistinguishable from a measured one the moment it is in the
# file.
LAST_DAY: str | None = None

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

HERE = Path(__file__).resolve().parent
STATE = Path(os.environ["WORKBENCH_STATE"])
ORACLE = HERE / "oracle.json"
BRIEF = HERE.parent / "instruction.md"

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_WEEKDAY_KEYS = tuple(name.capitalize() for name in _WEEKDAYS)
_MONTHS = (
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
_SENTENCE_ENDS = ".?!\r\n"

# Every number word English writes small, so that reading the brief's own
# list is a filter and not a second list to keep in step with it.
_SPELLED = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_BRIEF_DATE = re.compile(
    r"\b(" + "|".join(_WEEKDAYS) + r")\s+(\d{1,2})\s+(" + "|".join(_MONTHS) + r")"
    r"\s+(\d{4})\b",
    re.IGNORECASE,
)


def _fail(message: str) -> None:
    raise SystemExit(f"verify: {message}")


def brief() -> str:
    """The brief, refused outright while it still holds a placeholder.

    An unresolved authoring note is not a cosmetic problem here. This
    task's notes name the row floors, the solver and the scoring, and a
    brief that ships with them tells the agent what the task is trying to
    withhold. Nothing downstream can be checked against a brief that does
    not yet say what the window is, either.
    """

    text = BRIEF.read_text(encoding="utf-8")
    left = [line.strip() for line in text.splitlines() if "MEASURE" in line]
    if left:
        _fail(
            f"the brief still holds {len(left)} unmeasured value(s):\n  - "
            + "\n  - ".join(left[:6])
        )
    return text


def last_day(text: str) -> datetime.date:
    """The window's last day, read off the brief and not off the solver.

    The brief prints it as a weekday and a full date. Both halves are
    used: the date bounds the corpus, and the weekday name is checked
    against it, so a brief naming a day of the week that date is not
    fails here instead of shipping.
    """

    section = text.split("## The window", 1)
    if len(section) != 2:
        _fail("the brief has no '## The window' section to read the window from")
    found = _BRIEF_DATE.findall(section[1].split("\n## ", 1)[0])
    if len(found) != 1:
        _fail(
            f"the brief's window names {len(found)} weekday-and-date(s); it "
            "must name exactly one, as 'Friday 16 January 2026'"
        )
    name, day, month, year = found[0]
    date = datetime.date(int(year), _MONTHS.index(month.lower()) + 1, int(day))
    if _WEEKDAYS[date.weekday()] != name.lower():
        _fail(
            f"the brief calls {date} a {name}; it is a {_WEEKDAY_KEYS[date.weekday()]}"
        )
    return date


def numerals(text: str) -> dict[str, int]:
    """The words the brief admits after `within`, read off the brief.

    A word the solver accepts and the brief never names is a rule the
    agent was never told, and a word the brief names and the solver drops
    is a row the agent is graded for missing. This is where either shows.
    """

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "within" not in line.lower():
            continue
        cell = line.strip("|").split("|")[0]
        found = {
            token.lower(): _SPELLED[token.lower()]
            for token in re.findall(r"`([^`]+)`", cell)
            if token.lower() in _SPELLED
        }
        if not found:
            _fail(
                "the brief's `within` row names no number words. Write them "
                "backticked -- `a`, `two`, `three` -- so the list the agent "
                "reads and the list this checks are the same one."
            )
        return found
    _fail("the brief's form table has no `within` row")
    raise AssertionError("unreachable")


def _flatten(body: str) -> tuple[str, list[int]]:
    """Lowercased, whitespace-squashed text, plus each character's home.

    `index[k]` is where character `k` of the flattened text began in the
    original body, so a phrase found here reports the position the
    instruction asks for: a character count into the body as it comes
    back, line breaks and all.

    One character does not always lowercase to one character -- `İ` goes
    to two -- so the index is extended by the length of what was written
    and not by one. Appending a two-character string against a single
    index entry silently shifts every later position in that body, and
    `at` is the row key: the whole message would go missing from the
    register rather than come back wrong in a legible way.
    """

    flat: list[str] = []
    index: list[int] = []
    in_space = False
    for position, character in enumerate(body):
        if character.isspace():
            if in_space:
                continue
            written = " "
            in_space = True
        else:
            written = character.lower()
            in_space = False
        flat.append(written)
        index.extend([position] * len(written))
    return "".join(flat), index


def _wordish(character: str) -> bool:
    """A character a word can run through, underscore included.

    The solver's `\\b` counts `_` as part of a word; `str.isalnum` does
    not. On `EOD_draft.docx` that difference alone is a row here and no
    row there -- a disagreement over punctuation neither the brief nor
    anybody else ever chose.
    """

    return character.isalnum() or character == "_"


def _occurrences(flat: str, phrase: str):
    """Every standalone occurrence of a phrase, by flattened position."""

    start = 0
    while True:
        found = flat.find(phrase, start)
        if found < 0:
            return
        before = flat[found - 1] if found else " "
        after = flat[found + len(phrase)] if found + len(phrase) < len(flat) else " "
        if not _wordish(before) and not _wordish(after):
            yield found
        start = found + 1


def _word(token: str) -> str:
    """The token's leading word, ended where `\\b` would end it."""

    letters = []
    for character in token:
        if not _wordish(character):
            break
        letters.append(character)
    return "".join(letters)


def _next_weekday(sent: datetime.date, name: str) -> datetime.date:
    """Strictly after the sent date, found by walking."""

    day = sent + datetime.timedelta(days=1)
    while _WEEKDAYS[day.weekday()] != name:
        day += datetime.timedelta(days=1)
    return day


def _friday_of_week(sent: datetime.date) -> datetime.date:
    monday = sent
    while _WEEKDAYS[monday.weekday()] != "monday":
        monday -= datetime.timedelta(days=1)
    return monday + datetime.timedelta(days=4)


def _end_of_month(sent: datetime.date) -> datetime.date:
    first_of_next = (
        datetime.date(sent.year + 1, 1, 1)
        if sent.month == 12
        else datetime.date(sent.year, sent.month + 1, 1)
    )
    return first_of_next - datetime.timedelta(days=1)


def _found(
    body: str, sent: datetime.date, numbers: dict[str, int]
) -> dict[str, int]:
    """Each date the body names, and the leftmost form that names it.

    One entry per distinct date: two forms on the same date are one row,
    two forms on different dates are two, whatever the sentence around
    them is doing. `numbers` comes from the brief's own `within` row.
    """

    flat, index = _flatten(body)
    hits: list[tuple[int, datetime.date]] = []

    # `by Monday` ... `by Friday`, optionally with `this` or `next`. The
    # position is the `b` of `by`.
    for name in _WEEKDAYS[:5]:
        for phrase in (f"by {name}", f"by this {name}", f"by next {name}"):
            for at in _occurrences(flat, phrase):
                hits.append((index[at], _next_weekday(sent, name)))

    # `end of week` / `EOW` and `end of month` / `EOM`. Any of `by`,
    # `the`, `this`, `next` may sit in front and none of them moves the
    # position, which points at the form itself — so the optional words
    # need not be matched at all.
    for phrase in ("end of week", "eow"):
        for at in _occurrences(flat, phrase):
            hits.append((index[at], _friday_of_week(sent)))
    for phrase in ("end of month", "eom"):
        for at in _occurrences(flat, phrase):
            hits.append((index[at], _end_of_month(sent)))

    # `by <Month> <day>`, with or without an ordinal suffix, in the year
    # the message was sent. A date the calendar does not have makes no row.
    for number, month in enumerate(_MONTHS, start=1):
        for at in _occurrences(flat, f"by {month}"):
            rest = flat[at + len(f"by {month}") :]
            if not rest.startswith(" "):
                continue
            token = rest[1:].split(" ")[0]
            digits = ""
            for character in token:
                if not character.isdigit():
                    break
                digits += character
            if not digits or len(digits) > 2:
                continue
            tail = token[len(digits) :]
            if tail[:2] in ("st", "nd", "rd", "th"):
                tail = tail[2:]
            if tail[:1].isalnum():
                continue
            try:
                hits.append((index[at], datetime.date(sent.year, number, int(digits))))
            except ValueError:
                continue

    # `EOD`, `COB`, `end of day`, `close of business`: the sent date.
    for phrase in ("eod", "cob", "end of day", "close of business"):
        for at in _occurrences(flat, phrase):
            hits.append((index[at], sent))

    # `within N days` / `within N business days`: N calendar days on.
    for at in _occurrences(flat, "within"):
        rest = flat[at + len("within") :]
        if not rest.startswith(" "):
            continue
        parts = rest[1:].split(" ")
        raw = parts[0] if parts else ""
        count = _NUMBERS.get(raw, int(raw) if raw.isdigit() else None)
        if count is None:
            continue
        tail = parts[1:]
        if tail and tail[0] == "business":
            tail = tail[1:]
        if not tail or _leading_alpha(tail[0]) not in ("day", "days"):
            continue
        hits.append((index[at], sent + datetime.timedelta(days=count)))

    # `by tomorrow`: the day after.
    for at in _occurrences(flat, "by tomorrow"):
        hits.append((index[at], sent + datetime.timedelta(days=1)))

    leftmost: dict[str, int] = {}
    for position, due in hits:
        key = due.isoformat()
        if key not in leftmost or position < leftmost[key]:
            leftmost[key] = position
    return leftmost


def derive() -> dict:
    if LAST_DAY is None:
        raise SystemExit(
            "LAST_DAY is unmeasured. Transcribe the window from "
            "instruction.md as an ISO date. Deriving it from the solver "
            "instead would make this file agree with the solver by "
            "construction, which is the one thing it exists not to do."
        )
    last = datetime.date.fromisoformat(LAST_DAY)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    settings = dict(gmail.execute("SELECT key, value FROM meta"))
    epoch_day = datetime.datetime.fromisoformat(settings["epoch"]).date()
    names = dict(gmail.execute("SELECT person_id, name FROM people"))

    rows: list[dict] = []
    read = 0
    pairs = 0
    with_dates = 0
    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        # Whole days from the epoch's own date, then the calendar window
        # the instruction states — not the solver's seconds bound.
        sent = epoch_day + datetime.timedelta(days=int(when) // 86_400)
        if sent > last:
            continue
        read += 1
        leftmost = _found(body, sent)
        if not leftmost:
            continue
        with_dates += 1
        positions = sorted(leftmost.values())
        for first_index, first in enumerate(positions):
            for second in positions[first_index + 1 :]:
                between = body[first:second]
                if not any(character in _SENTENCE_ENDS for character in between):
                    pairs += 1
        for due, position in leftmost.items():
            rows.append(
                {
                    "ref": message_id,
                    "at": position,
                    "due_date": due,
                    "author": names[sender],
                    "sent_date": sent.isoformat(),
                }
            )

    rows.sort(key=lambda row: (row["ref"], row["at"]))
    weekdays = {key: 0 for key in _WEEKDAY_KEYS}
    authors: dict[str, int] = {}
    for row in rows:
        due = datetime.date.fromisoformat(row["due_date"])
        weekdays[_WEEKDAY_KEYS[due.weekday()]] += 1
        authors[row["author"]] = authors.get(row["author"], 0) + 1
    return {
        "messages_read": read,
        "rows_total": len(rows),
        "messages_with_dates": with_dates,
        "same_sentence_pairs": pairs,
        "distinct_authors": len(authors),
        "top_author": min(authors, key=lambda name: (-authors[name], name))
        if authors
        else None,
        "due_weekday_counts": weekdays,
        "dates": rows,
    }


def main() -> int:
    mine = derive()
    theirs = json.loads(ORACLE.read_text())
    problems: list[str] = []

    # The key, before anything else. A key that collapses two real rows
    # caps the achievable score below 1.0 for reasons no agent can fix,
    # and row F1 will not show it: both sides dedupe identically and it
    # still reads 1.000. So count the rows before and after keying, on
    # both the derivation and the committed oracle.
    for label, answer in (("derived", mine), ("oracle", theirs)):
        rows = answer["dates"]
        keyed = {(row["ref"], row["at"]) for row in rows}
        if len(keyed) != len(rows):
            problems.append(
                f"{label}: {len(rows)} rows collapse to {len(keyed)} under "
                "(ref, at) — the row key does not distinguish every row"
            )
    if len(mine["dates"]) < 12:
        problems.append(
            f"only {len(mine['dates'])} rows — below the floor at which "
            "partial credit can exist. Widen the window."
        )
    multi = len({row["ref"] for row in mine["dates"]})
    if len(mine["dates"]) - multi < 12:
        problems.append(
            f"only {len(mine['dates']) - multi} second-and-later rows — the "
            "composition this task measures is too thin to grade."
        )

    for field in (
        "messages_read",
        "rows_total",
        "messages_with_dates",
        "same_sentence_pairs",
        "distinct_authors",
        "top_author",
        "due_weekday_counts",
    ):
        if mine[field] != theirs.get(field):
            problems.append(
                f"{field}: derived {mine[field]!r}, oracle {theirs.get(field)!r}"
            )

    keyed_mine = {(row["ref"], row["at"]): row for row in mine["dates"]}
    keyed_theirs = {(row["ref"], row["at"]): row for row in theirs["dates"]}
    for key in sorted(set(keyed_mine) - set(keyed_theirs)):
        problems.append(f"row {key} derived here, absent from the oracle")
    for key in sorted(set(keyed_theirs) - set(keyed_mine)):
        problems.append(f"row {key} in the oracle, not derived here")
    for key in sorted(set(keyed_mine) & set(keyed_theirs)):
        for field in ("due_date", "author", "sent_date"):
            if keyed_mine[key][field] != keyed_theirs[key][field]:
                problems.append(
                    f"row {key} {field}: derived "
                    f"{keyed_mine[key][field]!r}, oracle "
                    f"{keyed_theirs[key][field]!r}"
                )

    if problems:
        print(f"{len(problems)} disagreement(s):")
        for problem in problems[:40]:
            print(f"  - {problem}")
        return 1
    print(
        f"independent derivation agrees: {len(mine['dates'])} rows across "
        f"{multi} messages, {mine['same_sentence_pairs']} same-sentence pairs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

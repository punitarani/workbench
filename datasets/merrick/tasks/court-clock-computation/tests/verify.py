"""An independent derivation of the court-clock register.

    uv run python datasets/merrick/tasks/court-clock-computation/tests/verify.py \
        [--world out/merrick/epoch/world.jsonl] [--oracle tests/oracle.json]

Everything here is transcribed from `instruction.md` — the prose the agent
is graded against — and from the raw world log. **Nothing is taken from
`solution/solve.py`.** Copying the solver's expression of a rule reproduces
its bug and then certifies that the two agree; two published scores in this
tree were the answer key rather than a measurement, certified exactly that
way.

**This file does not parse until every «MEASURE» is replaced**, for the same
reason `solve.py` does not: the vocabularies below are counts against the
corpus, and a plausible default is the defect. They are transcribed from the
instruction's own tables once those tables are filled in — read them there,
not from the solver.

## What is deliberately computed a second way

| the rule | solver | here |
|---|---|---|
| finding an interval form | three regexes over the raw body | a scan of whitespace-
split tokens |
| finding the first date form | every match collected, then sorted by start and length |
anchored match at each index, left to right, longest at the first index that hits |
| adding N days | one `timedelta(days=N)` | N single-day steps over the proleptic ordinal |
| moving a weekend landing | a `{Saturday: +2, Sunday: +1}` table | one-day steps while the day's *name* is Saturday or Sunday |
| which messages are in the window | a constant in seconds | the last day parsed out of
`instruction.md`, compared against a date walked forward from the epoch the world log
records |
| the date a message was sent | `epoch + timedelta(seconds=t)` | `t // 86_400` days walked forward from the epoch's date |

The window matters most. It is the one assumption the generator and the
solver both rest on, and their agreement is not evidence: shift the boundary
and every row moves together while every row-level check stays green. So it
is parsed from the prose here, and never from the solver's constant.

## What is necessarily shared, and therefore proves nothing

The *rule* itself — the three forms, the date-form table, the trigger,
day zero, the weekend move. An independence check cannot catch a rule that
disagrees with its own prose, because the rule is the specification both
derivations read. That is a different gate: `_phrasings()` below asserts
the transcription admits every example the instruction gives as admitted and
refuses every one it gives as refused.

The Slack `ts` string is also shared, because it is a projection convention
and not a rule: a chat message's reference is its absolute epoch second and
a per-second counter in log order. If that convention changes, both
derivations move together and neither notices — which is a reason to keep
`ref` reachable through the served tool, not a reason to re-invent it here.

## A known divergence, left in on purpose

Token scanning and `\\b`-anchored regexes disagree about hyphens. Splitting
on whitespace keeps `30-day` whole, so it names no interval either way — but
a body written `within 10-days` would be admitted by one scan and refused by
the other. A disagreement of that kind is adjudicated against
`instruction.md`, never by patching whichever side is easier to change.
"""
# ruff: noqa: E501
# Long lines are the «MEASURE» notes: the question a corpus has not
# been asked yet, written out in full because an abbreviated one gets
# guessed at instead of measured. They go when the values land.

import argparse
import calendar
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pending import measure  # noqa: E402

TASK = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- the rule
#
# Transcribed from `instruction.md`. Read it there; do not read `solve.py`.

SPELLED: dict[str, int] = measure("the spelled-out numbers `instruction.md` lists as…")

MONTHS: dict[str, int] = measure("the month spellings named by `instruction.md`'s dat…")

# Regexes for the date shapes `instruction.md` lists, each exposing named
# groups `month` and `day` and optionally `year`. Matched anchored at a
# position rather than searched, so the order of this tuple decides nothing.
DATE_FORMS: tuple[str, ...] = measure("the date shapes `instruction.md` lists, as anc…")

# The three interval forms, in the order the instruction's table lists them
# — which is the order `form_counts` resolves a body naming two of them for
# the same number.
UNITS = {"business", "calendar"}
DAY_WORDS = {"day", "days"}

# Examples the instruction itself gives. The rule must admit every phrase it
# calls a form and refuse every phrase it calls a near miss; a pattern
# narrower than the prose it implements fails here rather than in a rollout.
ADMITTED: tuple[tuple[str, str, int], ...] = (
    ("produce the privilege log within 10 days", "within N days", 10),
    ("objections are due 30 days after service", "N days after", 30),
    ("the opposition brief is due in 14 days", "due in N days", 14),
    ("within 10 days of service", "within N days", 10),
    ("due in 14 days or sooner", "due in N days", 14),
    ("we should be able to turn this around within 5 days", "within N days", 5),
    ("the standard clause gives them 30 days after notice", "N days after", 30),
    ("within 10 business days", "within N days", 10),
    ("within 10 calendar days", "within N days", 10),
    ("within 1 day", "within N days", 1),
)
REFUSED: tuple[str, ...] = (
    "within 2 weeks",
    "within 3 months",
    "we need 30 days' notice",
    "responses are due 30 days before the hearing",
    "I'll have it in 10 days",
    "a 30-day extension",
    "the 14 day window",
    "within a couple of days",
    "within the week",
    "the deposition is on 14 March",
)


# ------------------------------------------------------------- the reading


def _value(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return SPELLED.get(token)


def _tokens(body: str) -> list[str]:
    """Whitespace-split, with edge punctuation removed and hyphens kept.

    Hyphens stay inside a token deliberately: `30-day` is one word and names
    no interval, which is what the instruction says. Splitting on it would
    manufacture the adjacency `30 day` and admit rows nobody wrote.
    """

    out = []
    for raw in body.split():
        out.append(raw.strip(".,;:!?()[]{}<>\"'`").lower())
    return out


def _intervals(body: str) -> dict[int, str]:
    """Every distinct number of days the body names, and the form that named
    it — the first of the three in the instruction's order."""

    words = _tokens(body)
    found: dict[int, str] = {}

    def record(days: int | None, form: str) -> None:
        if days is None:
            return
        rank = {"within N days": 0, "N days after": 1, "due in N days": 2}
        if days not in found or rank[form] < rank[found[days]]:
            found[days] = form

    for i, word in enumerate(words):
        # `within N days`, `within N business days`, `within N calendar days`
        if word == "within":
            j = i + 2
            if j < len(words) and words[j] in UNITS:
                j += 1
            if j < len(words) and words[j] in DAY_WORDS:
                record(_value(words[i + 1]), "within N days")
        # `N days after`
        j = i + 1
        if j < len(words) and words[j] in UNITS:
            j += 1
        if j + 1 < len(words) and words[j] in DAY_WORDS and words[j + 1] == "after":
            record(_value(word), "N days after")
        # `due in N days`
        if word == "due" and i + 1 < len(words) and words[i + 1] == "in":
            j = i + 3
            if j < len(words) and words[j] in UNITS:
                j += 1
            if j < len(words) and words[j] in DAY_WORDS:
                record(_value(words[i + 2]), "due in N days")
    return found


_DATES = None


def _compiled() -> tuple[re.Pattern[str], ...]:
    global _DATES
    if _DATES is None:
        _DATES = tuple(re.compile(p, re.IGNORECASE) for p in DATE_FORMS)
    return _DATES


def _read_date(body: str, index: int, default_year: int) -> date | None:
    """The longest real date starting exactly at `index`, or None."""

    best: tuple[int, date] | None = None
    for pattern in _compiled():
        match = pattern.match(body, index)
        if match is None:
            continue
        parts = match.groupdict()
        month_text = (parts.get("month") or "").strip().lower()
        month = int(month_text) if month_text.isdigit() else MONTHS.get(month_text)
        if month is None:
            continue
        # Strip an ordinal suffix without a regex. The solver uses one, and
        # a second derivation that shares the pattern shares its bugs — the
        # instruction says "by March 14" and "by March 14th" are the same
        # date, so this checks the last two characters against the four
        # suffixes the language has.
        day_text = (parts.get("day") or "").strip()
        if day_text[-2:].lower() in {"st", "nd", "rd", "th"}:
            day_text = day_text[:-2]
        year_text = (parts.get("year") or "").strip()
        try:
            found = date(
                int(year_text) if year_text else default_year, month, int(day_text)
            )
        except ValueError:
            # Names no real day, so it is not a date form. A shorter
            # candidate at the same index may still be one.
            continue
        length = len(match.group(0))
        if best is None or length > best[0]:
            best = (length, found)
    return None if best is None else best[1]


def _trigger(body: str, sent: date) -> date:
    """Left to right, one index at a time: the first index at which any date
    form starts wins, and the longest form at that index is the trigger.

    Only word-start indices are tried. That is not a narrowing of the rule —
    every shape the instruction lists begins with a letter or a digit, and no
    match may begin part-way through a word — it is what keeps a
    character-by-character scan from costing minutes over a six-month corpus.
    """

    for index, char in enumerate(body):
        if not char.isalnum():
            continue
        if index and body[index - 1].isalnum():
            continue
        found = _read_date(body, index, sent.year)
        if found is not None:
            return found
    return sent


def _step(day: date, count: int) -> date:
    for _ in range(count):
        day = date.fromordinal(day.toordinal() + 1)
    return day


def _roll(raw: date) -> date:
    day = raw
    while calendar.day_name[day.weekday()] in {"Saturday", "Sunday"}:
        day = _step(day, 1)
    return day


# ------------------------------------------------------------- the window


def _window_last_day(instruction: str) -> date:
    """The last day of the window, parsed out of the instruction's prose.

    Never a constant, and never the solver's. A shifted boundary makes every
    row wrong together while every row-level check stays green, so the
    boundary is the one assumption that has to come from somewhere else.
    """

    match = re.search(
        r"sent\s+\*\*on or before\s+(?:[A-Za-z]+day\s+)?"
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\*\*",
        instruction,
    )
    if match is None:
        raise SystemExit(
            "instruction.md does not name a window in the expected form "
            '("sent **on or before Friday 16 January 2026**") — the '
            "boundary cannot be derived, so nothing here is trustworthy"
        )
    day, month_name, year = match.groups()
    months = {name.lower(): n for n, name in enumerate(calendar.month_name) if name}
    month = months.get(month_name.lower())
    if month is None:
        raise SystemExit(f"unknown month in the window sentence: {month_name!r}")
    return date(int(year), month, int(day))


# ------------------------------------------------------------- raw events


def _events(world_log: Path):
    with world_log.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _derive(world_log: Path, last_day: date) -> dict:
    epoch_dt: datetime | None = None
    names: dict[str, str] = {}
    messages: list[tuple[str, str, int, str]] = []
    per_second: Counter = Counter()

    for event in _events(world_log):
        payload = event.get("payload") or {}
        tag = event.get("tag")
        if tag == "sim.run.started":
            epoch_dt = datetime.fromisoformat(payload["epoch"])
        elif tag == "person.record":
            names[payload["person_id"]] = payload["name"]
        elif tag == "email.message":
            messages.append(
                (
                    payload["message_id"],
                    payload["sender"],
                    int(event["time"]),
                    payload["body"],
                )
            )
        elif tag == "chat.message":
            if epoch_dt is None:
                raise SystemExit(
                    f"{world_log}: a chat message precedes sim.run.started, so "
                    "the epoch a `ts` is built from is not known yet"
                )
            when = int(event["time"])
            # The projection's own convention, re-derived rather than read
            # out of the served table: absolute epoch second, then a
            # per-second counter in log order.
            absolute = int((epoch_dt + timedelta(seconds=when)).timestamp())
            ref = f"{absolute}.{per_second[when]:06d}"
            per_second[when] += 1
            messages.append((ref, payload["sender"], when, payload["body"]))

    if epoch_dt is None:
        raise SystemExit(f"{world_log} carries no sim.run.started event")
    epoch_day = epoch_dt.date()

    read = 0
    rows: list[dict] = []
    forms: list[str] = []
    for ref, sender, when, body in messages:
        # Whole days walked forward from the epoch's date, rather than a
        # seconds addition on an aware datetime.
        sent = _step(epoch_day, when // 86_400)
        if sent > last_day:
            continue
        read += 1
        trigger = _trigger(body, sent)
        for days, form in sorted(_intervals(body).items()):
            raw = _step(trigger, days)
            due = _roll(raw)
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
            forms.append(form)

    order = sorted(
        range(len(rows)), key=lambda i: (rows[i]["ref"], rows[i]["interval_days"])
    )
    rows = [rows[i] for i in order]
    forms = [forms[i] for i in order]

    by_form = {name: 0 for name in ("within N days", "N days after", "due in N days")}
    by_author: dict[str, int] = defaultdict(int)
    for row, form in zip(rows, forms, strict=True):
        by_form[form] += 1
        by_author[row["author"]] += 1

    return {
        "messages_read": read,
        "deadlines_total": len(rows),
        "distinct_authors": len(by_author),
        "rolled_count": sum(1 for row in rows if row["rolled"]),
        "form_counts": by_form,
        "busiest_author": (
            min(by_author, key=lambda name: (-by_author[name], name))
            if by_author
            else None
        ),
        "deadlines": rows,
    }


# ------------------------------------------------------------------ gates


def _phrasings() -> list[str]:
    """The rule admits its own examples, and refuses its own near misses."""

    problems = []
    for phrase, form, days in ADMITTED:
        found = _intervals(phrase)
        if found.get(days) != form:
            problems.append(
                f"instruction example not admitted as {form}/{days}: "
                f"{phrase!r} -> {found}"
            )
    for phrase in REFUSED:
        found = _intervals(phrase)
        if found:
            problems.append(f"near miss admitted: {phrase!r} -> {found}")
    return problems


def _tie_breaks() -> list[str]:
    """Orderings and tie-breaks, on a fixture, because real data rarely ties.

    Rollouts almost never exercise a tie, so a tie-break that disagrees with
    the instruction survives every sweep and then decides one row in the
    world that finally has one.
    """

    problems = []
    both = _intervals("within 10 days, and in any case due in 10 days")
    if both != {10: "within N days"}:
        problems.append(f"two forms, one number, should be one row: {both}")
    two = _intervals("within 10 days; the objection is 30 days after service")
    if set(two) != {10, 30}:
        problems.append(f"two numbers should be two rows: {two}")
    twice = _intervals("within 10 days -- again, within 10 days")
    if twice != {10: "within N days"}:
        problems.append(f"one form twice should be one row: {twice}")

    # Saturday 2026-03-14 rolls to Monday the 16th; Sunday the 15th to the
    # same Monday; Friday the 13th does not move.
    for day, expected in (
        (date(2026, 3, 14), date(2026, 3, 16)),
        (date(2026, 3, 15), date(2026, 3, 16)),
        (date(2026, 3, 13), date(2026, 3, 13)),
    ):
        got = _roll(day)
        if got != expected:
            problems.append(f"weekend move: {day} -> {got}, expected {expected}")
    # Day zero: ten days from Saturday 14 March is the 24th, not the 23rd.
    if _step(date(2026, 3, 14), 10) != date(2026, 3, 24):
        problems.append("the trigger day is day zero and the count is inclusive-of-0")
    # Longest form at the earliest index wins.
    if _trigger("filed March 14, 2026 and served March 20", date(2025, 1, 1)) != date(
        2026, 3, 14
    ):
        problems.append("the longest date form at the earliest index must win")
    # No date form at all falls back to the sent date.
    if _trigger("produce within 10 days", date(2026, 2, 2)) != date(2026, 2, 2):
        problems.append("a body with no date form must anchor on the sent date")
    return problems


def _keys_distinguish(rows: list[dict], label: str) -> list[str]:
    """`KEY` must separate every real row, on both sides.

    A key that collapses two rows caps the achievable score below 1.0 for
    reasons no agent can fix, and row F1 will not show it: both sides dedupe
    identically and it still reads 1.000.
    """

    keyed = {(row["ref"], str(row["interval_days"])) for row in rows}
    if len(keyed) != len(rows):
        return [f"{label}: {len(rows)} rows collapse to {len(keyed)} keys"]
    return []


def _compare(mine: dict, oracle: dict) -> list[str]:
    problems = []
    for field in sorted(set(mine) | set(oracle)):
        if field == "deadlines":
            continue
        if mine.get(field) != oracle.get(field):
            problems.append(
                f"{field}: derived {mine.get(field)!r}, oracle {oracle.get(field)!r}"
            )
    a = {(r["ref"], r["interval_days"]): r for r in mine["deadlines"]}
    b = {(r["ref"], r["interval_days"]): r for r in oracle["deadlines"]}
    for key in sorted(set(a) - set(b), key=str)[:20]:
        problems.append(f"row only in the second derivation: {key}")
    for key in sorted(set(b) - set(a), key=str)[:20]:
        problems.append(f"row only in the oracle: {key}")
    for key in sorted(set(a) & set(b), key=str):
        for field in ("author", "sent_date", "raw_due_date", "due_date", "rolled"):
            if a[key][field] != b[key][field]:
                problems.append(
                    f"{key} {field}: derived {a[key][field]!r}, "
                    f"oracle {b[key][field]!r}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="independent derivation")
    parser.add_argument("--world", type=Path, default=None)
    parser.add_argument("--oracle", type=Path, default=TASK / "tests" / "oracle.json")
    parser.add_argument("--instruction", type=Path, default=TASK / "instruction.md")
    args = parser.parse_args(argv)

    world = args.world
    if world is None:
        source = TASK / "bundle" / "SOURCE"
        if not source.is_file():
            raise SystemExit(
                "no --world and no bundle/SOURCE: build the task first, or "
                "point this at the world log the oracle was cut from"
            )
        world = Path(source.read_text().strip())
    if not world.is_file():
        raise SystemExit(f"no world log at {world}")

    problems = _phrasings() + _tie_breaks()
    if problems:
        # Stop here. A derivation from a rule that does not match its own
        # prose is not evidence about the oracle; it is a second copy of the
        # same mistake.
        print("the transcribed rule disagrees with instruction.md:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    last_day = _window_last_day(args.instruction.read_text())
    mine = _derive(world, last_day)
    oracle = json.loads(args.oracle.read_text())

    problems = _keys_distinguish(mine["deadlines"], "second derivation")
    problems += _keys_distinguish(oracle["deadlines"], "oracle")
    problems += _compare(mine, oracle)
    if problems:
        print(f"{len(problems)} disagreement(s) with the oracle:")
        for problem in problems[:60]:
            print(f"  {problem}")
        return 1

    print(
        f"agreed: {mine['deadlines_total']} rows over {mine['messages_read']} "
        f"messages through {last_day.isoformat()}, "
        f"{mine['rolled_count']} rolled"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

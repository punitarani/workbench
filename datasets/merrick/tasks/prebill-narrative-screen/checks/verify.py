"""An independent derivation of the prebill narrative screen.

    WORKBENCH_STATE=out/merrick/bundle/state python3 tests/verify.py

**Every rule below is transcribed from `instruction.md`** — the prose the
agent is graded against — and not from `solution/solve.py`. Copying the
solver's expression of a rule reproduces its bug and then certifies that
the two agree; two published scores in this tree were the answer key
rather than a measurement, certified exactly that way.

Where more than one computation is defensible, this file uses the one the
solver did not:

| quantity | solver | here |
|---|---|---|
| the window | day indices times 86,400 | the calendar dates the instruction names,
compared as dates |
| a narrative's date | `epoch + seconds`, then `.date()` | `epoch.date() + seconds // 86,400` days |
| the screen | one `re` search per admitted form | split the narrative into runs of
letters, test set membership |
| hours and fees | float division, `round` | exact `Fraction`, `Decimal.quantize` |
| the grouping | a `defaultdict` per figure | `sorted` then `itertools.groupby` |

The window gets its own derivation for the reason the template gives: a
boundary the generator and the solver both rest on is not checked by
their agreeing. A window shifted by one day makes every row wrong
together while every row-level check stays green.

**Sharing no code with the solver is not independence.** Every rule this
file expresses differently is still a rule it *hardcodes*, and so does
`solve.py`. Change the brief — say that `end of week` means the Sunday,
that a tie goes to the later name, that the window's last day is out —
and both derivations go on computing the old rule, agree perfectly, and
report an independent reading. So each hardcoded rule is written down
beside the words it was read off, in one table (`PINS`), and the run
stops when the brief stops saying them. What the brief states only inside
a «MEASURE» placeholder is not pinned: that text is a question, not an
answer, and it will be replaced wholesale.

**A pin holds on a sentence, never on a layout.** The brief is still
being edited, and a guard that fires when a paragraph is rewrapped, a
clause is bolded, a heading is recapitalised, a list is written with `*`
or its nested bullets indented four spaces is a guard that fires on every
honest edit and gets deleted for crying wolf — taking the rule it was
protecting with it. Everything read out of the brief therefore goes
through `flattened` or `_bullets` first, and the same is true of what is
read out of the deliverable's shape: `criteria_base` grades field names
as a set, so this file compares them as a set and a reordered bullet list
is not a finding.

Five things this file asserts that no per-row comparison can:

* **The key distinguishes every real row.** Not by counting rows before
  and after keying — rows are *built* by grouping on the key, on both
  sides, so that comparison is vacuous and can never fire. The collapse
  that can actually happen is upstream, in the columns the key is made
  of: two `ticket_id`s that share a `display_number`, or two `person_id`s
  that share a `name`, merge two people's real work into one row. That is
  what is checked here, along with the casefolded key `criteria_base`
  grades on. A collapsing key caps the ceiling below 1.0 for reasons no
  agent can fix, and row F1 reads 1.000 while it happens.
* **No figure lands exactly on a half at the second decimal**, so
  round-half-up and round-half-even cannot disagree, and the instruction
  is not obliged to name a rounding mode it never states.
* **The two rounding orders actually disagree *by more than the graded
  tolerance***, on the share the instruction quotes. A disagreement
  smaller than the tolerance in `criteria.py` is one the grader forgives,
  so counting it would certify a lever that does not move the score. If
  the share is short, the rule the instruction spends a paragraph on is
  decoration and the window or the grain is wrong.
* **The structural floors hold**: twelve rows or more, and no graded
  column carrying one value in every row.
* **The deliverable is shaped the way the brief bullets it.** The field
  names are read out of `## What to produce`, not restated: a field the
  brief renames would otherwise leave this file and the oracle agreeing
  on a key the agent was never given.

The key and the tolerances are read out of `criteria.py` rather than
restated, so the thing asserted here is the thing that grades.
"""
# ruff: noqa: E501
# Long lines are the «MEASURE» notes: the question a corpus has not
# been asked yet, written out in full because an abbreviated one gets
# guessed at instead of measured. They go when the values land.

import ast
import datetime
import itertools
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pending import measure  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
ORACLE = Path(__file__).resolve().parent / "oracle.json"
BRIEF = Path(__file__).resolve().parents[1] / "instruction.md"
DELIVERABLE = "prebill_screen.json"
BRIEF_TEXT = BRIEF.read_text(encoding="utf-8")


def refuse(message: str) -> NoReturn:
    """Stop the run.

    Kept apart from `bad` on purpose. `bad` collects a disagreement
    between this derivation and the oracle, which is a finding. This is a
    disagreement between this derivation and the *brief*, which is not a
    finding but a broken instrument: every number below it was computed
    from a rule the agent is no longer being given.
    """

    raise SystemExit(f"verify: {message}")


def flattened(chunk: str) -> str:
    """A piece of the brief with its emphasis, its backticks and its line
    wrapping taken out, so a phrase can be looked for without caring how
    the paragraph happened to break.

    Reflowing a paragraph, bolding a clause or putting a field name in
    backticks must not fire a pin; changing what the sentence says must.

    The delimiters are *deleted* rather than turned into spaces. Markdown
    emphasis abuts the words it marks, so italicising one word before a
    comma — `read the *words*, not the intent` — leaves a space in front
    of that comma under the substituting version, and a pin quoting the
    sentence stops matching a sentence that has not changed.
    """

    return " ".join(chunk.replace("*", "").replace("`", "").lower().split())


def section(heading: str) -> str:
    """One heading's worth of the brief, up to the next heading.

    Sections are found by their words, never by line number: the brief is
    still being written and every line in it will move.
    """

    found = re.search(re.escape(heading), BRIEF_TEXT, re.IGNORECASE)
    if not found:
        refuse(f"the brief has no {heading!r} section")
    return BRIEF_TEXT[found.end() :].split("\n## ", 1)[0]


_BULLET = re.compile(r"^(?P<indent>[ \t]*)[-*+][ \t]+(?P<body>.*)$")


def _bullets(chunk: str) -> list[tuple[int, tuple[str, ...]]]:
    """Every bullet of one section, as (depth, the field names it heads).

    Depth is 0 for the outermost bullets and 1 for anything indented
    under them, worked out from the indents the section actually uses
    rather than from a literal two spaces. A brief that indents its
    nested bullets four spaces, or writes `*` for `-`, or bolds the field
    name inside the bullet, is the same brief saying the same thing — and
    a reader that only recognises ``"- `"`` at column zero answers `()`
    to all three, silently, so the refusal that follows names the wrong
    problem.

    Only the head of the bullet is read — the part before its em dash —
    and only backticked names in it, so neither the prose describing a
    field nor a field mentioned in that prose contributes a name.
    """

    found: list[tuple[int, tuple[str, ...]]] = []
    for line in chunk.splitlines():
        marked = _BULLET.match(line)
        if not marked:
            continue
        head = marked["body"].split("—")[0].replace("*", "")
        found.append(
            (
                len(marked["indent"].expandtabs(4)),
                tuple(re.findall("`([a-z_]+)`", head)),
            )
        )
    outermost = min((depth for depth, _names in found), default=0)
    return [(0 if depth == outermost else 1, names) for depth, names in found]


def bulleted(chunk: str, depth: int) -> tuple[str, ...]:
    """The backticked field names the brief bullets at one depth, in
    written order."""

    return tuple(name for at, names in _bullets(chunk) if at == depth for name in names)


def nested_under(chunk: str) -> str:
    """The name of the field whose bullet owns the nested row columns —
    the brief's name for the list `criteria.py` grades row by row."""

    owner = ""
    for at, names in _bullets(chunk):
        if at == 0:
            owner = names[-1] if names else owner
        elif owner:
            return owner
    refuse("the brief bullets no field with row columns nested under it")


def form_rows(chunk: str) -> list[list[str]]:
    """The rows of the brief's form table, header and ruler dropped.

    How many rows it has is how many admitted forms this file must carry.
    Counting them here rather than writing `2` means a third row added to
    the brief becomes a third question this file refuses to run without,
    instead of a form it silently never looks for.
    """

    grid = [
        [cell.strip() for cell in line.strip()[1:-1].split("|")]
        for line in chunk.splitlines()
        if line.strip().startswith("|") and line.strip().endswith("|")
    ]
    if len(grid) < 3:
        refuse("the brief's form table has no header, no ruler or no rows")
    header, ruler, *rows = grid
    if [flattened(cell) for cell in header] != ["form", "matches"]:
        refuse(f"the brief's form table is headed {header}, not | form | matches |")
    if set("".join(ruler)) - set("-: "):
        refuse("the brief's form table has no ruler under its header")
    if any(len(row) != len(header) for row in rows):
        refuse("a row of the brief's form table is not two cells wide")
    return rows


class Pin(NamedTuple):
    """One rule of the brief, paired with what this file does about it.

    `heading` locates the sentence, `computes` names the arithmetic that
    only exists because the sentence says what it says, and `phrases` are
    the words that have to still be there.
    """

    heading: str
    computes: str
    phrases: tuple[str, ...]


# --- the phrase-to-code pairing, in one table ------------------------------
#
# Sharing nothing with the solver is not independence. This file and
# `solve.py` use different matchers, different arithmetic and different
# groupings, and they would still agree perfectly on every row if the
# brief changed the rule underneath both of them: the brief could start
# saying that a form only counts when the narrative means it, or that a
# tie goes to the *later* timekeeper, and both derivations would go on
# computing the old rule together while every row-level comparison stayed
# green. A second derivation cannot catch that by being a second
# derivation.
#
# So every rule this file hardcodes is written down here beside the words
# it was read off, in one table rather than scattered through the code,
# because a pin that lives away from what it pins is a pin that drifts.
# The pairing is checked before the first figure is computed.
#
# What is deliberately *not* pinned: the window's two dates, its
# working-day count, the admitted forms themselves, and the share of rows
# on which the two rounding orders must disagree. The brief states all
# five only inside «MEASURE» placeholders — text that is a question, not
# an answer, and that will be replaced wholesale when the corpus is
# measured. Anchoring on it would pin this file to wording that is
# guaranteed to change. They stay `measure()` calls, which refuse loudly
# on their own.
PINS: tuple[Pin, ...] = (
    Pin(
        "# The prebill narrative screen",
        "opening clio's `clio.db` and screening the `note` column of "
        "`activities`, and no other surface and no other column",
        (
            "tools: clio (matters, users and time entries)",
            "the screen reads time entries and nothing else",
            "the narrative is the note recorded on the entry",
            "is not a time entry and makes no row here",
        ),
    ),
    Pin(
        "## The window",
        "requiring both endpoints to be weekdays and counting a working "
        "day as `weekday() < 5`",
        ("screen only time recorded on the working days from",),
    ),
    Pin(
        "## The window",
        "`FIRST <= day <= LAST`, with both endpoints inside the window",
        (
            "the window is its two endpoints",
            "inclusive",
            "on or after the first day and on or before the last day is in scope",
            "a single day either side of the span is out",
        ),
    ),
    Pin(
        "## The window",
        "no weekday test at all on an entry that falls inside the span",
        ("whatever weekday it carries",),
    ),
    Pin(
        "## The window",
        "`read += 1` only after the window filter, never before it",
        (
            "entries_read counts the time entries inside the window",
            "there is no need to open the rest of the firm's timekeeping",
        ),
    ),
    Pin(
        "## What the screen admits",
        "lowercasing both sides and testing membership anywhere in the note",
        ("matched case-insensitively", "anywhere in the text"),
    ),
    Pin(
        "## What the screen admits",
        "`whole_words`, which splits the narrative into runs of letters",
        (
            "a form is a whole word",
            "no letter immediately before it and no letter immediately after it",
            "a digit, a hyphen, a slash or a punctuation mark is not a letter",
        ),
    ),
    Pin(
        "## What the screen admits",
        "no sense test — an off-sense narrative is flagged like any other",
        ("the test is textual, not editorial", "read the words, not the intent"),
    ),
    Pin(
        "## What the screen admits",
        "set membership, which cannot be vetoed by the words around the form",
        (
            "a form inside a longer phrase still counts",
            "the words around it do not remove it",
        ),
    ),
    Pin(
        "## What the screen admits",
        "membership in `ADMITTED` alone — no synonym, no other inflection",
        (
            "nothing else counts",
            "no synonym counts",
            "no other form of the word counts",
            "a narrative carrying only one of those is not flagged",
        ),
    ),
    Pin(
        "## What the screen admits",
        "one `flagged` row and one `forms[...] += 1` per time entry",
        (
            "one flagged entry per time entry",
            "however many admitted forms its narrative carries and however many times",
        ),
    ),
    Pin(
        "## What the screen admits",
        "`carried[0]`, which resolves a multi-form narrative to the "
        "earliest row of the table",
        ("under whichever form is listed first in the table above",),
    ),
    Pin(
        "## Which matters are in scope",
        "no matter filter — the firm's own standing codes screen like any client's",
        (
            "every matter the firm records time to",
            "time booked to them is time, it is screened the same way",
        ),
    ),
    Pin(
        "## The arithmetic",
        "`Fraction(quantity, 3600)`",
        ("quantities are recorded in seconds", "hours are seconds ÷ 3600"),
    ),
    Pin(
        "## The arithmetic",
        "`Fraction(rate_cents, 100) * hours`, computed entry by entry",
        (
            "rates are dollars per hour",
            "recorded against the individual entry",
            "an entry's fee is the rate on that entry times that entry's hours",
            "fees are per entry, not per person and not per matter",
        ),
    ),
    Pin(
        "## The arithmetic",
        "the fee predicate `billable and rate_cents is not None`, and both "
        "of its clauses",
        (
            "an entry contributes to fees_dollars only when it is billable and has a rate",
            "some time is recorded non-billable",
            "some timekeepers carry no rate at all",
            "this holds even for an entry marked billable that has no rate on it",
        ),
    ),
    Pin(
        "## The arithmetic",
        "hours and entry counts taken over every flagged entry, rated or not",
        (
            "everything flagged contributes to entries and to hours",
            "it belongs in entries and in hours",
            "their entries belong in entries and in hours too",
        ),
    ),
    Pin(
        "## The arithmetic",
        "exact `Fraction` accumulation and a single `Decimal.quantize` at write time",
        (
            "round once, at the end — every figure, not only the totals",
            "are computed from the time entries themselves",
            "rounded to two decimal places only when they are written",
            "not computed by adding up figures that have already been cut to two decimals",
        ),
    ),
    Pin(
        "## What to produce",
        "comparing the keys of `mine` against every field the brief "
        "bullets, with nothing missing and nothing unasked-for",
        ("one file in your workspace", "with exactly these fields"),
    ),
    Pin(
        "## What to produce",
        "`read`, incremented for every entry in the window whatever its note says",
        ("every entry inside the window, whatever its narrative says",),
    ),
    Pin(
        "## What to produce",
        "`entries_flagged` as `len(flagged)` — flagged entries, not "
        "flagged matters and not flagged occurrences",
        ("how many of those the screen admits",),
    ),
    Pin(
        "## What to produce",
        "`hours_total` summed over every flagged entry and "
        "`fees_total_dollars` over the billable-and-rated ones, both from "
        "the exact per-row figures",
        (
            "the flagged hours, all of them, 2 dp",
            "what the flagged time comes to, 2 dp",
        ),
    ),
    Pin(
        "## What to produce",
        "`pairs` as `len(rows)`",
        ("how many matter-and-timekeeper combinations appear in screened",),
    ),
    Pin(
        "## What to produce",
        "`{form: forms.get(form, 0) for form in admitted}`, zeros included",
        (
            "an object with every form in the table above as a key",
            "including any that no narrative in the window uses",
            "how many flagged entries carry it",
        ),
    ),
    Pin(
        "## What to produce",
        "`min(rows, key=(-hours, matter, timekeeper))` — most hours, then "
        "the earlier name in each tie column",
        (
            "the single row in screened with the most hours",
            "break a tie by taking the earlier matter",
            "then the earlier timekeeper",
            "alphabetically",
        ),
    ),
    Pin(
        "## What to produce",
        "grouping on `(matter, timekeeper)` and emitting only groups with a flag",
        (
            "one entry per matter-and-timekeeper combination with at least one flagged entry",
            "makes no row",
        ),
    ),
    Pin(
        "## What to produce",
        "`flagged.sort(key=(matter, timekeeper))` before `groupby`",
        ("sorted by matter then timekeeper",),
    ),
    Pin(
        "## What to produce",
        "keying rows on clio's `display_number` and the person's `name`",
        (
            "the matter's display number, exactly as clio shows it",
            "the person's full name",
            "how many flagged entries they recorded on that matter",
        ),
    ),
)


def insists(pin: Pin) -> None:
    """Refuse unless the brief still states the rule this file computes.

    Prose cannot be executed: `whole_words` splits on letters because the
    brief says a form is bounded by letters, and nothing here reads that
    sentence and works the split out. What *can* be checked is that the
    sentence has not moved out from under the arithmetic — which is the
    one failure a second derivation cannot catch by being a second
    derivation, because the solver hardcodes the same rule and the two go
    on agreeing with each other while both disagree with the brief.
    """

    flat = flattened(section(pin.heading))
    missing = [phrase for phrase in pin.phrases if flattened(phrase) not in flat]
    if missing:
        refuse(
            f"the brief's {pin.heading!r} no longer says {missing[0]!r}.\n"
            f"This file computes {pin.computes} because that sentence said "
            "so, and it does not read the sentence — so does solve.py, which "
            "is why the oracle would still agree with this derivation on "
            "every row while both disagreed with the brief the agent is "
            "graded against. Read the brief again and move the derivation "
            f"to match.\n  brief now: {flat[:280]}"
        )


for _pin in PINS:
    insists(_pin)

if DELIVERABLE not in BRIEF_TEXT:
    refuse(f"the brief never names {DELIVERABLE}")

# The deliverable's shape, read off the brief's own bullets rather than
# restated here. A field the brief renames is otherwise invisible: this
# file and the oracle would keep the old name, agree, and grade an agent
# on a key it was never given.
REPORT_FIELDS: tuple[str, ...] = bulleted(section("## What to produce"), 0)
ROW_FIELDS: tuple[str, ...] = bulleted(section("## What to produce"), 1)
ROW_LIST: str = nested_under(section("## What to produce"))

# How many rows the brief's form table carries. Not `2`: see `form_rows`.
FORMS_STATED = len(form_rows(section("## What the screen admits")))

# --- transcribed from instruction.md, "The window" -------------------------
# The two calendar dates the brief names, as ISO. Written here as dates and
# not as offsets on purpose: this is the half of the boundary the solver
# does not compute.
WINDOW_FIRST = measure("instruction.md's window first day, as YYYY-MM-DD")
WINDOW_LAST = measure("instruction.md's window last day, as YYYY-MM-DD")
WORKING_DAYS = measure("the working-day count instruction.md states for that span")

# --- transcribed from instruction.md, "What the screen admits" -------------
# The table's rows, in the table's order. The instruction fixes the
# multi-form tie by "whichever form is listed first in the table above",
# so the order is part of the rule and not presentation.
#
# One question per row the brief actually shows, counted above rather than
# written out here. A form the brief adds and this file never asks for
# would count zero in `form_counts` with nothing complaining.
ADMITTED: tuple[str, ...] = tuple(
    measure(f"instruction.md's admitted form {number}")
    for number in range(1, FORMS_STATED + 1)
)

_PENDING = [
    str(v)
    for v in (WINDOW_FIRST, WINDOW_LAST, WORKING_DAYS, *ADMITTED)
    if "«MEASURE" in str(v)
]
if _PENDING:
    raise SystemExit(
        "verify.py still carries «MEASURE» placeholders and will not run:\n  - "
        + "\n  - ".join(_PENDING)
        + "\nTranscribe them from instruction.md — from the brief the agent "
        "reads, never from solve.py."
    )

FIRST = datetime.date.fromisoformat(WINDOW_FIRST)
LAST = datetime.date.fromisoformat(WINDOW_LAST)
CENT = Decimal("0.01")

# `whole_words` below reduces a narrative to its runs of letters and tests
# set membership, so a form carrying anything that is not a letter — a
# hyphen, an apostrophe, a space — can never be a member and every entry
# that really carries it goes unflagged. That failure is silent: it does
# not raise, it just produces a smaller answer that then disagrees with
# the oracle on dozens of rows, and reads like a solver bug. Refuse
# instead. The letters-only boundary in instruction.md is what makes this
# representation legitimate, and it only holds for single-run forms.
_MALFORMED = [form for form in ADMITTED if not re.fullmatch("[A-Za-z]+", form)]
if _MALFORMED:
    raise SystemExit(
        "these admitted forms are not single runs of letters: "
        + ", ".join(repr(form) for form in _MALFORMED)
        + "\nThe screen here matches whole words by set membership and "
        "cannot see a form containing a hyphen, an apostrophe or a space. "
        "Either choose single-word forms or rewrite `whole_words`."
    )


def _criteria_constant(name: str):
    """Read one constant out of `criteria.py` without importing it.

    `criteria.py` does `from criteria_base import *`, and `criteria_base`
    imports `rewardkit` and reads `oracle.json` at module scope — neither
    is available while the oracle is still being built, which is exactly
    when this file runs. Parsing the assignment is enough.

    Reading them beats restating them: the key and the tolerances checked
    here are then literally the ones that grade, and a change to
    `criteria.py` cannot leave this file quietly asserting the old ones.
    """

    source = (Path(__file__).resolve().parent / "criteria.py").read_text()
    for node in ast.parse(source).body:
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else getattr(node, "targets", [])
        )
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"criteria.py defines no {name}")


ROWS: str = _criteria_constant("ROWS")
KEY: tuple[str, ...] = tuple(_criteria_constant("KEY"))
TOLERANCE: dict[str, float] = _criteria_constant("FIELDS")

problems: list[str] = []


def bad(message: str) -> None:
    problems.append(message)


def money(value: Fraction) -> float:
    """Two decimals, rounded half *up* — the mode the solver does not use.

    Legitimate only alongside `halves`, below: if no figure lands on an
    exact half, this and the solver's round-half-even agree everywhere,
    and the instruction's silence about the mode costs nobody anything.
    """

    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return float(exact.quantize(CENT, rounding=ROUND_HALF_UP))


def is_half(value: Fraction) -> bool:
    """True when the value sits exactly on a 2 dp rounding boundary."""

    scaled = value * 1000
    return scaled.denominator == 1 and scaled.numerator % 10 == 5


def whole_words(narrative: str) -> set[str]:
    """The narrative as a set of lowercased runs of letters.

    instruction.md: a form counts when there is "no letter immediately
    before it and no letter immediately after it". Splitting on
    everything that is not a letter says the same thing by construction —
    a hyphen, a slash or a digit ends a run, so a hyphenated compound
    yields its parts and carries the form. The solver runs one bounded
    regex per form instead; these agree only if the boundary rule is the
    one both were told.
    """

    return {run.lower() for run in re.findall("[A-Za-z]+", narrative)}


def main() -> int:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    meta = dict(clio.execute("SELECT key, value FROM meta"))
    epoch = datetime.datetime.fromisoformat(meta["epoch"])

    # The day-floor route below is only the same as the served
    # `epoch + seconds` route when the epoch is local midnight. Assert it
    # rather than assume it: if it ever moves, the two derivations differ
    # for real and this file should say so instead of quietly agreeing.
    if (epoch.hour, epoch.minute, epoch.second) != (0, 0, 0):
        bad(f"epoch {meta['epoch']} is not local midnight; the date routes diverge")

    if FIRST.weekday() > 4 or LAST.weekday() > 4:
        bad(f"window endpoints {FIRST}..{LAST} are not both working days")
    if LAST < FIRST:
        bad(f"window {FIRST}..{LAST} runs backwards")
    span = (LAST - FIRST).days + 1
    working = sum(
        1
        for offset in range(span)
        if (FIRST + datetime.timedelta(days=offset)).weekday() < 5
    )
    if working != int(WORKING_DAYS):
        bad(
            f"instruction.md says {WORKING_DAYS} working days; {FIRST}..{LAST} "
            f"holds {working}"
        )

    names = dict(clio.execute("SELECT person_id, name FROM people"))
    matters = dict(clio.execute("SELECT ticket_id, display_number FROM matters"))
    admitted = list(ADMITTED)
    if len(set(admitted)) != len(admitted):
        bad(f"instruction.md's form table repeats a form: {admitted}")

    read = 0
    flagged: list[tuple[str, str, Fraction, Fraction]] = []
    forms: Counter[str] = Counter()
    epoch_day = epoch.date()
    # The identity behind each key column, for the collapse check. A row
    # is keyed on a display number and a person's *name*, but the work is
    # recorded against a `ticket_id` and a `person_id`. If two ids ever
    # share a rendered value, two rows of real work merge into one and
    # nothing downstream can tell.
    matter_ids: dict[str, set[str]] = defaultdict(set)
    person_ids: dict[str, set[str]] = defaultdict(set)

    for ticket, person, quantity, note, when, rate_cents, billable in clio.execute(
        "SELECT ticket_id, person, quantity_seconds, note, time, rate_cents, billable"
        " FROM activities"
    ):
        # The instruction's window is two inclusive calendar endpoints,
        # and it says explicitly that the weekday of an entry inside the
        # span does not matter. No weekday filter here, deliberately.
        day = epoch_day + datetime.timedelta(days=when // 86_400)
        if not FIRST <= day <= LAST:
            continue
        read += 1
        words = whole_words(note)
        carried = [form for form in admitted if form.lower() in words]
        if not carried:
            continue
        # "an entry carrying more than one form counts once, under
        # whichever form is listed first in the table above"
        forms[carried[0]] += 1
        hours = Fraction(quantity, 3600)
        # "An entry contributes to fees_dollars only when it is billable
        # *and* has a rate."
        fee = (
            Fraction(rate_cents, 100) * hours
            if billable and rate_cents is not None
            else Fraction(0)
        )
        matter_ids[matters[ticket]].add(ticket)
        person_ids[names[person]].add(person)
        flagged.append((matters[ticket], names[person], hours, fee))

    flagged.sort(key=lambda row: (row[0], row[1]))
    rows = []
    exact: list[tuple[Fraction, Fraction]] = []
    round_then_sum_disagreements = 0
    for (matter, timekeeper), group in itertools.groupby(
        flagged, key=lambda row: (row[0], row[1])
    ):
        members = list(group)
        hours = sum((m[2] for m in members), Fraction(0))
        fee = sum((m[3] for m in members), Fraction(0))
        exact.append((hours, fee))
        rows.append(
            {
                "matter": matter,
                "timekeeper": timekeeper,
                "entries": len(members),
                "hours": money(hours),
                "fees_dollars": money(fee),
            }
        )
        # The number instruction.md quotes: how often adding figures that
        # were each already cut to two decimals gives a different row.
        #
        # Measured against the graded tolerance, not against exact
        # inequality. A row whose two orders differ by less than the
        # tolerance in `criteria.py` is a row the grader marks correct
        # either way, so counting it would certify a difficulty lever
        # that cannot move a score. Only a gap the grader would actually
        # reject counts here.
        hours_gap = abs(round(sum(money(m[2]) for m in members), 2) - money(hours))
        fees_gap = abs(round(sum(money(m[3]) for m in members), 2) - money(fee))
        if hours_gap > TOLERANCE.get("hours", 0.0) or fees_gap > TOLERANCE.get(
            "fees_dollars", 0.0
        ):
            round_then_sum_disagreements += 1

    total_hours = sum((h for h, _f in exact), Fraction(0))
    total_fees = sum((f for _h, f in exact), Fraction(0))

    halves = [
        value
        for value in [total_hours, total_fees, *(v for pair in exact for v in pair)]
        if is_half(value)
    ]
    if halves:
        bad(
            f"{len(halves)} figure(s) land exactly on a 2 dp half, so the "
            "rounding mode decides an answer the instruction never names"
        )

    heaviest = min(
        rows, key=lambda r: (-r["hours"], r["matter"], r["timekeeper"]), default=None
    )
    mine = {
        "entries_read": read,
        "entries_flagged": len(flagged),
        "pairs": len(rows),
        "hours_total": money(total_hours),
        "fees_total_dollars": money(total_fees),
        "form_counts": {form: forms.get(form, 0) for form in admitted},
        "heaviest_matter": heaviest and heaviest["matter"],
        "heaviest_timekeeper": heaviest and heaviest["timekeeper"],
        "screened": rows,
    }

    # --- the checks a per-row comparison cannot make -----------------------
    # The brief's own bullets, against the dict written just above. A
    # renamed field is invisible to every other check in this file: the
    # oracle carries the old name too, and the two agree.
    #
    # `refuse` and not `bad`, for two reasons. It is a broken instrument
    # rather than a finding, and everything below reaches into a row by
    # the column names read off the brief — collecting the problem and
    # carrying on turns a clear message into a `KeyError` twenty lines
    # later.
    # Compared as sets and not as ordered tuples: `criteria_base.schema_ok`
    # grades `set(got) == TOP`, and `row_fields` looks each column up by
    # name, so the order a field is written in is graded nowhere. Ordered
    # comparison would refuse over a reordered bullet list — a change to
    # how the brief reads and not to what it asks for.
    absent = [field for field in REPORT_FIELDS if field not in mine]
    surplus = [field for field in mine if field not in REPORT_FIELDS]
    if absent or surplus:
        refuse(
            f"instruction.md bullets {list(REPORT_FIELDS)}; this derivation "
            f"writes {list(mine)} — missing {absent}, unasked-for {surplus}"
        )
    if rows and set(rows[0]) != set(ROW_FIELDS):
        refuse(
            f"instruction.md's row columns are {list(ROW_FIELDS)}; this "
            f"derivation writes {list(rows[0])}"
        )
    key = KEY
    # Also `refuse`: `key` indexes every row from here down, and `ROWS`
    # names the list the oracle is read out of. Collecting either and
    # carrying on reaches a `KeyError`, or an empty oracle list that
    # looks like a real disagreement.
    if ROWS != ROW_LIST:
        refuse(
            f"criteria.py grades rows named {ROWS!r}; the brief bullets {ROW_LIST!r}"
        )
    if set(key) - set(ROW_FIELDS):
        refuse(f"criteria.py keys rows on {key}, which the brief does not bullet")

    # Counting `rows` before and after keying proves nothing: `rows` is
    # built by grouping on `key`, so the two counts are equal by
    # construction — as they are in `solve.py`, which builds from a dict
    # keyed the same way. The collapse that can really happen is one
    # level up, where two distinct records render to the same key column.
    for display, tickets in sorted(matter_ids.items()):
        if len(tickets) > 1:
            bad(
                f"display number {display!r} covers {len(tickets)} matters "
                f"({', '.join(sorted(tickets))}) — their rows merge and no "
                "agent can unmerge them"
            )
    for name, ids in sorted(person_ids.items()):
        if len(ids) > 1:
            bad(
                f"timekeeper {name!r} is {len(ids)} people "
                f"({', '.join(sorted(ids))}) — their rows merge and no agent "
                "can unmerge them"
            )
    # `criteria_base._keyed` strips and casefolds every key column, so two
    # rows differing only in case or surrounding space are one row to the
    # grader even when they are two rows here.
    graded_key = Counter(
        tuple(str(row[k]).strip().casefold() for k in key) for row in rows
    )
    for collision, count in sorted(graded_key.items()):
        if count > 1:
            bad(
                f"{count} rows share the graded key {collision} once stripped "
                "and casefolded; the grader sees one row and the ceiling drops"
            )
    if len(rows) < 12:
        bad(f"only {len(rows)} rows — too thin to express partial credit")
    for field in ROW_FIELDS:
        if rows and len({row[field] for row in rows}) == 1:
            bad(f"screened.{field} carries one value in all {len(rows)} rows")
    if sum(mine["form_counts"].values()) != len(flagged):
        bad("form_counts does not sum to entries_flagged")
    if len(flagged) != sum(row["entries"] for row in rows):
        bad("entries_flagged does not sum from the rows")
    share = round_then_sum_disagreements / len(rows) if rows else 0.0
    if share < 0.20:
        bad(
            f"the two rounding orders disagree beyond tolerance on {share:.1%} "
            "of rows — under a fifth, so the paragraph instruction.md spends "
            "on the order is decoration; widen the window or coarsen the grain"
        )

    print(f"window      {FIRST}..{LAST} ({working} working days)")
    print(f"screen      {admitted}")
    print(f"entries     {read} read, {len(flagged)} flagged")
    print(
        f"rows        {len(rows)}  hours {mine['hours_total']}  "
        f"fees {mine['fees_total_dollars']}"
    )
    print(f"graded      rows={ROWS} key={KEY} tol={TOLERANCE}")
    print(
        f"rounding    {round_then_sum_disagreements}/{len(rows)} rows differ "
        f"({share:.1%}) beyond tolerance between sum-then-round and "
        "round-then-sum"
    )

    if not ORACLE.is_file():
        bad(f"no oracle at {ORACLE} to compare against")
    else:
        truth = json.loads(ORACLE.read_text())
        if set(truth) != set(mine):
            bad(f"oracle keys {sorted(truth)} != derived keys {sorted(mine)}")
        for field in sorted(set(truth) & set(mine) - {ROWS}):
            if truth[field] != mine[field]:
                bad(f"{field}: oracle {truth[field]!r} != derived {mine[field]!r}")

        # Keyed the way `criteria_base._keyed` keys, stripped and
        # casefolded, so this lookup is the grader's lookup rather than a
        # stricter one that would pass while grading fails.
        def graded(row: dict) -> tuple[str, ...]:
            return tuple(str(row.get(k)).strip().casefold() for k in key)

        oracle_rows = truth.get(ROWS, [])
        theirs = {graded(r): r for r in oracle_rows}
        if len(theirs) != len(oracle_rows):
            bad(
                f"the oracle's own {len(oracle_rows)} rows collapse to "
                f"{len(theirs)} under the graded key {key}"
            )
        ours = {graded(r): r for r in rows}
        for missing in sorted(set(theirs) - set(ours)):
            bad(f"oracle row {missing} is not in the derived answer")
        for extra in sorted(set(ours) - set(theirs)):
            bad(f"derived row {extra} is not in the oracle")
        for shared in sorted(set(theirs) & set(ours)):
            for field in ("entries", "hours", "fees_dollars"):
                if theirs[shared][field] != ours[shared][field]:
                    bad(
                        f"row {shared} {field}: oracle "
                        f"{theirs[shared][field]!r} != derived "
                        f"{ours[shared][field]!r}"
                    )

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nindependent derivation agrees with the oracle")
    return 0


if __name__ == "__main__":
    sys.exit(main())

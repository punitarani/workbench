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

Four things this file asserts that no per-row comparison can:

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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pending import measure  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
ORACLE = Path(__file__).resolve().parent / "oracle.json"

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
ADMITTED: tuple[str, ...] = (
    measure("instruction.md's admitted form 1"),
    measure("instruction.md's admitted form 2"),
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
    key = KEY
    if ROWS != "screened":
        bad(f"criteria.py grades rows named {ROWS!r}; the deliverable has 'screened'")
    if set(key) - {"matter", "timekeeper"}:
        bad(f"criteria.py keys rows on {key}, which is not the row grain here")

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
    for field in ("entries", "hours", "fees_dollars", "matter", "timekeeper"):
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

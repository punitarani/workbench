"""Reference solver: the prebill narrative screen.

One rule, three ways to get it wrong, and the last two are the reason
this task exists rather than being a second copy of the word-family
register.

**The screen is literal.** A narrative is flagged when it carries one of
the admitted spellings as a whole word, whatever the sentence is doing
with it. The corpus writes the same act in several near-synonyms and
several other inflections of the same root, and every one of those stays
out. That part is the sibling dataset's shape, transplanted from message
bodies to time-entry narratives — a different corpus, and its vocabulary
has to be counted there rather than assumed from the mail.

**The population split is stated in prose and absent from the schema.**
Hours count every flagged entry. Dollars count only the entries the firm
can actually charge, and there are two independent reasons an entry
cannot be: it is non-billable, or its timekeeper carries no rate at all.
The report has `hours` and `fees_dollars` and nothing named
`billable_hours` or `unrated_hours`, deliberately — a schema that names
each half of a distinction has handed the distinction over, which is
what made `self-review-exposure` score 1.000 three times.

Do not overstate what that buys. The *deliverable* keeps the split
unnamed, but the *served surface* does not: `list_activities` returns
`total=None` when `rate_cents is None or not billable`, which is exactly
the complement of the fee predicate below. An agent that never reads the
paragraph, and simply skips entries whose `total` is null, lands on the
right population. So this split grades arithmetic discipline — hours over
everything, dollars over the rated-and-billable subset, each summed from
`quantity` and `price` rather than from the pre-rounded `total` — and not
the reading of the prose. The prose is what makes it *followable*; the
difficulty lives in the rounding order.

**The rounding order is the served fields' trap.** `list_activities`
hands back `quantity_in_hours` and `total` already rounded to two
decimals. Summing them is round-then-sum, and it is wrong. Every figure
here is computed from `quantity_seconds` and `rate_cents` and rounded
once, when it is written.

Every «MEASURE» below is a value this world has not finished recording.
The guard beneath them refuses to run rather than let a guessed window
or a guessed word family produce an oracle that looks exactly like a
measured one — which is the defect this tree has paid for most.
"""
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("prebill_screen.json")

# Day indices from the epoch, zero-based: day 0 is the first working day
# of the record. The window is inclusive of both endpoints, so the
# exclusive second-offset bound is one day past the last.
#
# Held as day indices and not as parsed dates on purpose: the world's
# clock is seconds-from-epoch and a date string here would need a
# timezone the record does not repeat. `tests/verify.py` goes the other
# way — from the calendar dates the instruction names — precisely so that
# a shifted boundary cannot pass unnoticed. A boundary the solver and the
# oracle share is not checked by their agreeing.
# --- the family screen over notes, probed at day 30 of 130 -----------
#
# This task inherits a 60% off-sense bar from a pure-literalism register.
# A first pass over 2,663 time-entry notes did not find a family that
# clearly clears it:
#
#   review   944 sentences    ~2% off-sense
#   draft    576             ~3%
#   file     262            ~13%
#   call     209            ~53%   <- best, and misread; see below
#
# `call` leads only because the probe counted "Call with client re Renwick
# non-compete" as off-sense. It is not: a call with a client is the
# timekeeper performing the act, which is exactly the register's idea. The
# genuine off-sense for `call` is the noun standing for an event rather than
# an act -- "per the call", "call notes", "ahead of the call" -- and that is
# a smaller set. Treat 53% as an upper bound that has not been earned.
#
# **The bar may be the wrong question here.** 60% was set for a register
# whose entire difficulty is refusing to generalise a closed word set. This
# task carries a second axis the other does not: it aggregates hours and
# fees by (matter, timekeeper), so a reader who admits the right sentences
# can still get the arithmetic wrong, and one who admits the wrong ones
# produces totals that are wrong twice. A task with two independent sources
# of difficulty does not need either to carry the whole band.
#
# **Measured, and it points the other way.** The two halves are not
# independent, so they cannot be traded against each other -- the sums are
# computed *from* the admitted set, and the row key is (matter, timekeeper)
# rather than the entry. One misadmitted entry therefore does not add or drop
# a row the way it would in a per-row register. It lands inside a pair that
# is otherwise correct and moves that pair's `hours` and `fees_dollars`.
#
#   283 (matter, timekeeper) pairs over 2,663 entries
#   entries per pair: median 7, mean 9.4, max 78
#   one entry as a share of its pair's hours: median 12%, p25 6.9%
#   tolerance on `hours`: 0.011 -- forty seconds
#
# At that tolerance essentially **any** misadmission fails `hours`, and
# `fees_dollars` with it: two of the three graded fields on a row the reader
# got right. A fifth of pairs hold a single entry, where the same error also
# moves the row set and so row F1 as well.
#
# So the scoring here amplifies admission error rather than diluting it, and
# the inherited 60% bar is not merely unnecessary -- it is aimed the wrong
# way. A family at 40-50% off-sense will produce more score movement in this
# task than a 60% family produces in a per-row register. The live risk is the
# opposite of the one the bar guards against: too *hard*, landing under 0.2,
# because a model with good-but-imperfect admission loses two fields on every
# pair it touches.
#
# What to do with that: take the best family the notes actually offer, state
# the measured share in the brief rather than a bar it did not clear, and
# read the first sweep for scores that are too low rather than too high. If
# they are, the lever is the tolerance on `hours` -- forty seconds is a
# rounding rule, not a difficulty knob, and widening it to something like a
# tenth of an hour restores partial credit for a nearly-right pair.
#
# Timekeeper notes are a different corpus from message bodies -- shorter,
# written to be billed, and far more uniform. A family that clears 60% in
# mail (`confirm` does, at 66%) says nothing about what clears it here.

WINDOW_FIRST_DAY = measure("zero-based day index of the window's first working day")
WINDOW_LAST_DAY = measure("zero-based day index of the window's last working day")

# In this order: the first that matches names the entry's form, so a
# narrative carrying two of them is still one flagged entry with one
# name. The order here IS the order of the table in `instruction.md`;
# they must not drift apart, because the instruction fixes the tie that
# way and an agent can only follow what it was told.
#
# measure("the admitted forms. Run the family screen over activities.note inside the window and take the family whose hand-classified off-sense share is highest, and at least 60%")
FORMS: tuple[tuple[str, str], ...] = (
    (measure("admitted form 1"), measure("admitted form 1")),
    (measure("admitted form 2"), measure("admitted form 2")),
)

_PENDING = [
    str(value)
    for value in (
        WINDOW_FIRST_DAY,
        WINDOW_LAST_DAY,
        *(w for pair in FORMS for w in pair),
    )
    if "«MEASURE" in str(value)
]
if _PENDING:
    raise SystemExit(
        "solve.py still carries «MEASURE» placeholders and will not run:\n  - "
        + "\n  - ".join(_PENDING)
        + "\nMeasure them against the recorded world first. A solver that "
        "runs on a guessed window writes an oracle nothing can distinguish "
        "from a measured one."
    )

WINDOW_START = WINDOW_FIRST_DAY * 86_400
WINDOW_END = (WINDOW_LAST_DAY + 1) * 86_400


def _whole_word(word: str) -> re.Pattern[str]:
    """A form, bounded by letters rather than by `\\b`.

    The difference is about digits, underscores and hyphens. `\\b` treats
    `review2` and `review_x` as boundary matches, and a corpus carrying
    matter numbers and reference codes produces rows an instruction
    cannot justify. Letters-only is also the rule a brief can state in
    one sentence — "no letter immediately before it and no letter
    immediately after" — which is the version the agent is graded
    against, and it is what makes a hyphenated compound carry the form.
    """

    return re.compile(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", re.IGNORECASE)


_PATTERNS = tuple((name, _whole_word(word)) for name, word in FORMS)


def _form(narrative: str) -> str | None:
    for name, pattern in _PATTERNS:
        if pattern.search(narrative):
            return name
    return None


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    people = dict(clio.execute("SELECT person_id, name FROM people"))
    matters = dict(clio.execute("SELECT ticket_id, display_number FROM matters"))

    read = 0
    entries: dict[tuple[str, str], int] = defaultdict(int)
    seconds: dict[tuple[str, str], int] = defaultdict(int)
    # Fees accumulate in cents-times-seconds, an integer, and are divided
    # by 3600 exactly once at the end. Not because the float would drift
    # far, but because "round once at the end" is the rule the
    # instruction states and the oracle should be the rule rather than a
    # close approximation of it.
    fee_cent_seconds: dict[tuple[str, str], int] = defaultdict(int)
    by_form: dict[str, int] = {name: 0 for name, _word in FORMS}

    for ticket, person, quantity, note, when, rate_cents, billable in clio.execute(
        "SELECT ticket_id, person, quantity_seconds, note, time, rate_cents, billable"
        " FROM activities"
    ):
        if not WINDOW_START <= when < WINDOW_END:
            continue
        # Counted only inside the window. Requiring a figure over the
        # whole record is what turns a task into no deliverable at all:
        # the agent goes and reads the whole record to produce it. The
        # bound has to apply to the work, not only to the answer.
        read += 1
        form = _form(note)
        if form is None:
            continue
        by_form[form] += 1
        row = (matters[ticket], people[person])
        entries[row] += 1
        seconds[row] += quantity
        # Two independent reasons an entry carries no money, and the
        # instruction states both: non-billable time is written off, and
        # a timekeeper with no rate has nothing to charge at. Neither
        # touches the hours.
        if billable and rate_cents is not None:
            fee_cent_seconds[row] += rate_cents * quantity

    rows = [
        {
            "matter": matter,
            "timekeeper": timekeeper,
            "entries": entries[(matter, timekeeper)],
            "hours": round(seconds[(matter, timekeeper)] / 3600, 2),
            "fees_dollars": round(
                fee_cent_seconds[(matter, timekeeper)] / 100 / 3600, 2
            ),
        }
        for matter, timekeeper in sorted(entries)
    ]

    OUT.write_text(
        json.dumps(
            {
                "entries_read": read,
                "entries_flagged": sum(entries.values()),
                "pairs": len(rows),
                # From the entries, not from the rows. Summing the row
                # figures is the round-then-sum the instruction forbids,
                # and it is the answer an agent gets for free by adding
                # up the served `quantity_in_hours` and `total`.
                "hours_total": round(sum(seconds.values()) / 3600, 2),
                "fees_total_dollars": round(
                    sum(fee_cent_seconds.values()) / 100 / 3600, 2
                ),
                # Every listed form, including any the window never uses.
                # Emitting only the forms that occur would make "does a
                # zero belong in the object?" a judgement the instruction
                # never settles, and an answer can be marked wrong for
                # guessing it either way.
                "form_counts": {name: by_form[name] for name, _word in FORMS},
                # Most hours, then the earlier matter, then the earlier
                # name. `max` breaks both ties the other way and the
                # instruction says earlier. Compared on the reported 2 dp
                # figure, which is what the instruction names.
                "heaviest_matter": min(
                    rows, key=lambda r: (-r["hours"], r["matter"], r["timekeeper"])
                )["matter"],
                "heaviest_timekeeper": min(
                    rows, key=lambda r: (-r["hours"], r["matter"], r["timekeeper"])
                )["timekeeper"],
                "screened": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

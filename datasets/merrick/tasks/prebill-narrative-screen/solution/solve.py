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

import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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
WINDOW_FIRST_DAY = measure("zero-based day index of the window's first working day")
WINDOW_LAST_DAY = measure("zero-based day index of the window's last working day")

# In this order: the first that matches names the entry's form, so a
# narrative carrying two of them is still one flagged entry with one
# name. The order here IS the order of the table in `instruction.md`;
# they must not drift apart, because the instruction fixes the tie that
# way and an agent can only follow what it was told.
#
# measure("the admitted forms. Run the family screen over # `activities.note` inside…")
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

"""RETIRED. Do not build this task; the corpus carries neither half of its rule.

It needs an interval form (`within N days`) and a calendar date in one
body. Measured across the record: **zero and zero**. Not hard --
impossible, and a model finding none of the rows would have read as a
model that could not do date arithmetic.

Reference solver: the clock each named deadline runs on.

Three interval forms, an anchor taken from the first date the same body
names, and a weekend landing moved to the Monday after it. The register is
arithmetic, not judgement — which is what makes it measurable and what
makes it hard in the one place that matters: the anchor. A model that finds
`within 10 days` and counts from the day the mail was sent gets a row that
is present, keyed correctly, and wrong in all three computed fields.

**This file will not import until every `measure()` below is answered.**
That is deliberate. Every one of them is a number or a vocabulary that has
to be counted against the recorded corpus, and the failure this dataset
pays for most is an author supplying one from intuition. A call that raises
with the open question attached is a cheap way to make that impossible; a
plausible default is not.

Run `datasets/merrick/measure_candidates.py --state out/merrick/bundle/state
--days N` for the date-form density, and extend it with the three interval
forms below — the screens it already prints are for a word-family register
and a seven-form promise register, neither of which is this shape.

## One reading that was chosen, and can be flipped

The rule as briefed said a row needs an interval form **and** a date form
in the same body, and also that the trigger is the sent date when no date
form appears. Both cannot hold: a conjunction makes the fallback
unreachable, and an unreachable branch in an instruction is prose a careful
reader stops to puzzle over.

Taken here as: **the interval form admits the row; the date form supplies
the trigger, and must be in the same body rather than in the thread or the
subject; the sent date stands in when the body names none.** That is what
`instruction.md` says, and it is how a docket clerk actually reads a
letter. Requiring both instead is one predicate in `_rows_for` and one
paragraph in the instruction. The count that decides it is how many
in-window bodies carry an admitted interval form and no date form: if that
is a small share the fallback is dead prose and the conjunction is the
better rule, and if it is a large one the conjunction throws away most of
the register.
"""

# --- viability, measured on the recording in progress -----------------
#
# **This task has no rows yet.** Day 12 of 130, 523 messages: `within N
# days`, `N days after`, `N days from` and `due in N days` occur **zero**
# times, and so does any `<Month> <day>` date. Both halves of a row are
# absent, not just one.
#
# If that holds at 130 days this task **retires**. It does not get
# widened: admitting `a month` or `two weeks` to manufacture rows trades
# a task whose rule the firm does not write for a task whose rule nobody
# stated, and the register would be measuring the author's vocabulary
# rather than the model.
#
# The replacement should use a mechanism this corpus demonstrably
# carries. `EOD`/`COB`/`close of business` appears in 104 of 523
# messages — three quarters of all form hits — which is a real
# concentration and a different shape from anything else in the suite.
# The `measure()` questions below are written out whole, and wrapped as
# implicitly concatenated strings rather than shortened to fit a line. An
# abbreviated question gets guessed at instead of measured, which is the one
# thing this mechanism exists to refuse. They go when the values land.

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# The dataset root, which is where `pending.py` is. `parents[2]` is the
# `tasks/` directory and has no module in it, so importing from there raises
# ModuleNotFoundError instead of the `Unmeasured` that names the question
# still open — the failure the sentinel exists to produce.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pending import measure  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("court_clock.json")

# The window's length in calendar days from the epoch, in the world's own
# seconds. A message is in the window when its `time` is strictly less than
# this. `time` on a served row is seconds since the world's epoch and not a
# date: comparing its string form against an ISO date compiles, runs, and
# windows on a lexicographic accident.
#
# This has to match the day named in `instruction.md` exactly. It is the one
# assumption the solver and the verifier both rest on, so `checks/verify.py`
# re-derives it from the instruction's prose rather than from this constant.
CUTOFF = (
    measure(
        "the window's length in calendar days from 2026-01-05, the same day "
        "`instruction.md` names as its last"
    )
    * 86_400
)

# What may stand where `N` goes, beyond digits. Counted against the corpus,
# never guessed: a list naming a word the firm does not write admits
# nothing, and a list missing one it writes often scores every instance of
# that word as a hallucination — which is how one register admitted 1 of 35
# real instances and reported the other 34 as inventions.
SPELLED: dict[str, int] = measure(
    "the spelled-out numbers that actually appear inside one of the three "
    "interval forms in this corpus, mapped to their integer value. Screen at "
    "least: a, one, two, three, four, five, seven, ten, fourteen, twenty, "
    "thirty, sixty, ninety"
)

# The three forms, in the order `form_counts` reports them. First match in
# this order names a row's form, so a body carrying two forms for the same
# number is still one row with one name.
#
# `{n}` is substituted with the number alternation. `days?` is deliberate:
# `instruction.md` says `day` and `days` read alike, so `within 1 day` and
# `within 10 days` carry the same form.
FORM_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("within N days", r"\bwithin\s+({n})\s+(?:business\s+|calendar\s+)?days?\b"),
    ("N days after", r"\b({n})\s+(?:business\s+|calendar\s+)?days?\s+after\b"),
    ("due in N days", r"\bdue\s+in\s+({n})\s+(?:business\s+|calendar\s+)?days?\b"),
)

# Before anything else is filled in, count how many in-window bodies carry
# each of these three forms. A literalism register is only hard where the
# near-misses are dense, and it is only a *task* where the admitted form is
# live at all. Measured on the partial worlds available while this was
# written, two of the three were dead and the third was close to it, against
# a corpus that writes its deadlines as a weekday and a numeric date with a
# parenthetical countdown beside them. If that holds on the finished record,
# the three forms above are the wrong three and the register should be cut
# from the shapes the firm actually writes -- changing the rule, not the
# window, is what fixes a dead vocabulary.

# Month spellings this corpus writes, mapped to month number. Abbreviations
# are a separate count from the full names and are only in this table if the
# firm actually uses them.
MONTHS: dict[str, int] = measure(
    "the month spellings that appear in this corpus, full and abbreviated, "
    "lowercased, mapped to 1-12"
)

# Every date shape the register recognises, as a regex. The contract each
# one must satisfy: named groups `month` and `day`, optionally `year`, and a
# word boundary at both ends. `month` is either a key of MONTHS or a
# one-or-two-digit number.
#
# The boundaries are not decoration. This scan is `finditer` over the whole
# body and will happily match part-way through a token — `PO4/17` yields
# `4/17` — while `checks/verify.py` only tries indices at the start of a
# word. A shape written without `\b` therefore reads a trigger here that the
# second derivation cannot see, and the disagreement surfaces as a row whose
# dates are wrong for no reason either file explains.
#
# Order does not decide anything here — the trigger is chosen by position in
# the body and then by length, not by which pattern is listed first — so
# this tuple may be written in whatever order reads best.
DATE_FORMS: tuple[str, ...] = measure(
    "the written date shapes this corpus actually uses, as regexes exposing "
    "named `month`, `day` and optional `year`, each bounded by a word "
    "boundary at both ends. Screen `March 14`, `March 14th`, `14 March`, "
    "`March 14, 2026`, `2026-03-14`, `3/14` and `3/14/2026` separately; a "
    "shape the firm never writes costs nothing to omit, and one it writes "
    "often and the list omits turns every such message into a wrong trigger "
    "rather than a missing row. Numeric `M/D` needs its own look before it "
    "goes in: this firm's traffic uses the same characters for item "
    "numbering (`#15/16`), for score-like pairs, and for a docket date. The "
    "month-range check in `_trigger` is what keeps `15/16` out, and it is "
    "load-bearing rather than defensive -- count how many `M/D` tokens in "
    "the corpus are not dates before deciding the shape is safe"
)


def _number_alternation() -> str:
    # Longest first, so `fourteen` is not eaten by `four`.
    words = sorted(SPELLED, key=len, reverse=True)
    return "|".join([r"\d+", *(re.escape(word) for word in words)])


FORMS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(template.format(n=_number_alternation()), re.IGNORECASE))
    for name, template in FORM_TEMPLATES
)
DATES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in DATE_FORMS
)


def _value(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return SPELLED.get(token)


def _trigger(body: str, sent: datetime.date) -> datetime.date:
    """The first date form in the body, or the sent date when there is none.

    Earliest start wins; where two forms start together the longer one wins,
    so `March 14, 2026` beats the `March 14` inside it. A candidate naming a
    day the calendar does not have is not a date form at all — it is skipped
    and the next one is considered, exactly as the instruction says.
    """

    candidates = []
    for pattern in DATES:
        for match in pattern.finditer(body):
            candidates.append((match.start(), -len(match.group(0)), match))
    for _start, _length, match in sorted(candidates, key=lambda c: c[:2]):
        parts = match.groupdict()
        raw_month = (parts.get("month") or "").strip().lower()
        month = int(raw_month) if raw_month.isdigit() else MONTHS.get(raw_month)
        if month is None:
            continue
        day_text = re.sub(r"(?i)(st|nd|rd|th)$", "", (parts.get("day") or "").strip())
        year_text = (parts.get("year") or "").strip()
        year = int(year_text) if year_text else sent.year
        try:
            return datetime.date(year, month, int(day_text))
        except ValueError:
            # February 30 names no day, so it is not a date form. Fall
            # through to the next candidate rather than to the sent date:
            # a body can name a bad date and then a good one.
            continue
    return sent


def _rows_for(body: str) -> dict[int, str]:
    """Every distinct interval the body names, mapped to its form's name.

    One row per *number*, not per occurrence and not per form: `within 10
    days` twice is one row, and `within 10 days` beside `due in 10 days` is
    one row named by the first form in `FORMS` order.
    """

    found: dict[int, str] = {}
    for name, pattern in FORMS:
        for match in pattern.finditer(body):
            days = _value(match.group(1))
            if days is None:
                continue
            found.setdefault(days, name)
    return found


def _roll(raw: datetime.date) -> datetime.date:
    # Saturday is 5 and Sunday is 6; the Monday after each is +2 and +1.
    # Only these two move a date — this register keeps no holiday calendar.
    shift = {5: 2, 6: 1}.get(raw.weekday(), 0)
    return raw + datetime.timedelta(days=shift)


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    slack = sqlite3.connect(f"file:{STATE / 'slack.db'}?mode=ro", uri=True)

    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    read = 0
    rows: list[dict] = []
    forms: list[str] = []

    def collect(ref: str, sender: str, when: int, body: str) -> None:
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        trigger = _trigger(body, sent)
        for days, form in _rows_for(body).items():
            # The trigger day is day zero, so the count is a plain addition.
            raw = trigger + datetime.timedelta(days=days)
            due = _roll(raw)
            rows.append(
                {
                    "ref": ref,
                    "author": people[sender],
                    "sent_date": sent.isoformat(),
                    "interval_days": days,
                    "raw_due_date": raw.isoformat(),
                    "due_date": due.isoformat(),
                    "rolled": due != raw,
                }
            )
            forms.append(form)

    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        if when >= CUTOFF:
            continue
        # Counted inside the window only. A `messages_read` defined over the
        # whole corpus is what turns a solvable task into no deliverable at
        # all: the agent reads six months of traffic to report one integer
        # and runs out of budget before it writes anything. Bound the work,
        # not only the answer.
        read += 1
        collect(message_id, sender, when, body)
    for ts, sender, when, body in slack.execute(
        "SELECT ts, sender, time, body FROM messages"
    ):
        if when >= CUTOFF:
            continue
        read += 1
        collect(ts, sender, when, body)

    order = sorted(
        range(len(rows)), key=lambda i: (rows[i]["ref"], rows[i]["interval_days"])
    )
    rows = [rows[i] for i in order]
    forms = [forms[i] for i in order]

    # Every listed form, including any the window happens not to carry.
    # Emitting only the forms that occur makes "does a zero belong in the
    # object?" a judgement the instruction never settles, and an answer can
    # then be marked wrong for guessing it either way.
    by_form: dict[str, int] = {name: 0 for name, _template in FORM_TEMPLATES}
    by_author: dict[str, int] = defaultdict(int)
    for row, form in zip(rows, forms, strict=True):
        by_form[form] += 1
        by_author[row["author"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "deadlines_total": len(rows),
                "distinct_authors": len(by_author),
                "rolled_count": sum(1 for row in rows if row["rolled"]),
                # Reported in the order the instruction lists the forms, not
                # alphabetically: `form_counts` is compared whole, and the
                # instruction's own table is the only order a reader has.
                "form_counts": {name: by_form[name] for name, _ in FORM_TEMPLATES},
                # Most rows, then the earlier name. `max` breaks the tie the
                # other way and the instruction says earlier first.
                #
                # `None` on an empty register rather than a traceback: a
                # window that yields no rows is a build to abandon, and the
                # degeneracy report in `build_tasks.py` is what says so
                # ("deadlines is EMPTY -- there is nothing to find"). A
                # `min()` over an empty dict kills the build three steps
                # earlier with a message about iterables.
                "busiest_author": (
                    min(by_author, key=lambda name: (-by_author[name], name))
                    if by_author
                    else None
                ),
                "deadlines": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

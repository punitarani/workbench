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
are compared casefolded. `re-«FORM_B»` yields the token «FORM_B» either
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

STATE = Path(os.environ.get("WORKBENCH_STATE", ""))
ORACLE = Path(__file__).resolve().parent / "oracle.json"

# --- transcribed from instruction.md ------------------------------------

# "The term is one word in two spellings: «FORM_A» and «FORM_B»."
FORM_A = "«FORM_A»"
FORM_B = "«FORM_B»"
# "Report only messages sent on or before <weekday date>" -- the inclusive
# last day, as a date, in the firm's own time zone.
LAST_DAY = measure("the same boundary instruction.md states, as YYYY-MM-DD")
# "in the firm's own time zone (New York)"
FIRM_TZ = "America/New_York"
# "an object with one key per department the directory records"
DEPARTMENTS: tuple[str, ...] = ()
# "One file in your workspace: word_register.json, with exactly these fields"
TOP_FIELDS = frozenset(
    {
        "messages_read",
        "hits_total",
        "distinct_authors",
        "form_counts",
        "department_counts",
        "top_author",
        "hits",
    }
)
ROW_FIELDS = ("ref", "author", "sent_date", "where")

# Letters, digits and the underscore continue a word; everything else ends
# one.
_SPLIT = re.compile(r"[^0-9A-Za-z_]+")


def _unbuilt() -> str | None:
    if "«" in FORM_A or "«" in FORM_B:
        return "FORM_A/FORM_B"
    if "«" in LAST_DAY:
        return "LAST_DAY"
    if not DEPARTMENTS:
        return "DEPARTMENTS"
    return None


def _forms_in(body: str) -> set[str]:
    tokens = {token.casefold() for token in _SPLIT.split(body) if token}
    return {form for form in (FORM_A, FORM_B) if form.casefold() in tokens}


def _named_form(body: str) -> str | None:
    """A message carrying both forms counts once, under «FORM_A»."""

    present = _forms_in(body)
    if FORM_A in present:
        return FORM_A
    return FORM_B if FORM_B in present else None


def _fail(problems: list[str]) -> int:
    for problem in problems:
        print(f"  MISMATCH  {problem}")
    print(f"\n{len(problems)} disagreement(s) between instruction.md and the oracle.")
    return 1


def main() -> int:
    if (missing := _unbuilt()) is not None:
        raise SystemExit(
            f"off-sense-register: {missing} is still a placeholder. Transcribe "
            "it from instruction.md once the family and the window are "
            "measured -- and read it off the instruction, not off solve.py."
        )
    if not STATE.is_dir():
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
    last_day = datetime.date.fromisoformat(LAST_DAY)

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
        if (form := _named_form(body)) is None:
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
        if (form := _named_form(body)) is None:
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
    by_form = {FORM_A: 0, FORM_B: 0} | Counter(named)
    by_department = dict.fromkeys(DEPARTMENTS, 0)
    # Reported, never raised. A roster short by one, and a name that does not
    # join between the mail directory and iManage, are the two defects this
    # second route exists to catch; indexing straight into either dict raises
    # KeyError, which aborts before a single check() runs and prints a
    # traceback where the finding belongs.
    roster: list[str] = []
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

    if set(truth) != TOP_FIELDS:
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
    if len(rows) < 12:
        problems.append(f"row floor: {len(rows)} rows, fewer than 12")
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

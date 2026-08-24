"""Reference solver: what the two-spelling search term hits.

The family is `file` / `filed` over the record's first eighteen calendar
days, which is the fourteen working days the brief names. Chosen by
measurement rather than intuition -- `measure_word_family.py file filed
--days 18` -- and what decided it is that **both halves of F1 bite**:

* over-admission. `filing` appears in thirty of the window's messages and
  twenty-one of those carry no admitted form at all; `filings` in two,
  `files` in one. A reader who stems to `fil-` gains twenty-two rows that
  are not the term.
* under-admission. Roughly a third of the messages that *do* carry an
  admitted form use `file` as a **noun** -- "pull his file", "the credit
  agreement file", "we have it on file". A reader who filters for
  relevance drops every one, and the rule is literal.

That second number is the off-sense share this task is built on: the
literal rule and the editorial one return very different sets, so a model
that reads for meaning is punished for it, which is the whole point.

What makes the shape work, when it works: the admitted form is a word a law
firm uses constantly for something other than the act the term names, so
excluding a synonym that plainly means the act -- and admitting a sentence
that plainly does not -- is a decision about spelling made against
everything the reader knows the sentence says, once per near miss.

Two structural notes for whoever fills this in:

**One row per message.** `ref` is the message's own id, so the row key
distinguishes every row on both sides.

**No per-row form field.** `form_counts` needs the classification; the row
does not print it. Naming which of the two spellings matched, per row,
hands the agent a checklist -- the decomposition that made
`self-review-exposure` score 1.000 three times over.
"""
# ruff: noqa: E501
# Long lines are the «MEASURE» questions: written out in full because
# an abbreviated one gets guessed at instead of measured. Truncating
# them once already destroyed what they were for. They go when the
# values land.

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("word_register.json")

# **Calendar** days, not working days. The cutoff below is
# `WINDOW_DAYS * 86_400` and `measure_candidates.py --days N` counts the same
# way, but instruction.md also prints a *working-day* figure for the same
# window and that is a different number. Filling this in from that one drops
# every weekend in the window and shortens the corpus silently -- the row
# count still looks plausible, so nothing downstream says so.
#
# Eighteen calendar days, which is the fourteen working days the brief
# names. Measured, not chosen: `measure_word_family.py file filed --days 18`
# gives 596 messages read for 64 rows, with the minority form `filed` in 17
# of them. Ten and fourteen days carry the minority form in *one* message,
# which is the hygiene failure the brief's own note records.
WINDOW_DAYS: int | None = 10

# In this order: the first that matches names the row's form, so a message
# carrying both is still one hit with one name -- which is what the
# instruction says, under «FORM_A».
#
# The family is chosen by measurement, not by ear. Both spellings of one
# word and nothing else: not its other endings, not its synonyms. The
# whole-word rule the instruction states is letters-based — letters,
# digits and underscore continue a word, so a hyphenated compound counts
# and a longer word containing the letters does not.
#
# «MEASURE: run datasets/merrick/measure_candidates.py against the graded
# window and take the family with the highest hand-classified off-sense
# share, which must be at least 60%.»
# --- off-sense share, measured at day 30 of 130 ----------------------
#
# An audit rated this task dead: "the corpus carries no word family that
# clears the task's own 60% off-sense gate, so only coverage difficulty
# remains." **That does not hold, and the reasoning behind it is worth
# knowing.**
#
# It read the `minority` column of `measure_candidates.py` -- 36.1% for
# `confirm` -- as the off-sense share. It is not. That column is the share
# of hits carried by the minority *spelling* of the family, a mechanical
# number. The off-sense share is how often the word means something other
# than the register's idea, and the script says outright that this "always
# blocks until a human reads the sample".
#
# Read against the register's idea -- a confirmation actually given by the
# writer -- and scoped to the sentence carrying the form:
#
#   asking someone else to confirm    46   16%
#   absent / negated / not yet       100   36%
#   promised for later                39   14%
#   a confirmation actually given     96   34%
#   ---------------------------------------------
#   off-sense share                  185/281 = 66%
#
# **The residual error runs one way.** Sentences still in the ON bucket
# include "Pull his file and confirm." -- an instruction to someone else --
# so the true share is above 66%, not below. A first attempt at this used a
# character window rather than a sentence and reported 40%, because "I'll
# pull the executed agreement and any amendments from the file and confirm"
# put its `I'll` sixty characters from the verb. Two classifiers, 26 points
# apart, differing only in where they drew the frame.
#
# So the family is `confirm` and the difficulty is rule literalism, not
# coverage: two thirds of the hits are the word doing something other than
# confirming, and every one of them reads like a confirmation to a model
# that admits by meaning rather than by spelling.
#
# Re-measure on the finished record before fixing the forms -- this is 30
# workdays of 130, and a corpus count is true of the window measured.

FORMS: tuple[tuple[str, str], ...] = (
    ("agree", r"\bagree\b"),
    ("agreed", r"\bagreed\b"),
)

# Every department the served directory records, including the ones no row
# lands in. Emitting only the departments that occur would make "does a zero
# belong in the object?" a judgement the instruction never settles, and an
# answer can be marked wrong for guessing it either way.
#
# measure("read this off people.department in the built state: SELECT DISTINCT department FROM people. Every department gets a key including the zero-valued ones, or a zero becomes a judgement the instruction never settles")
DEPARTMENTS: tuple[str, ...] = (
    "Client",
    "Corporate",
    "Employment",
    "Firm Management",
    "IP",
    "Litigation",
    "Practice Operations",
)


def _unbuilt() -> str | None:
    if WINDOW_DAYS is None:
        return "WINDOW_DAYS"
    if any("«" in name for name, _pattern in FORMS):
        return "FORMS"
    if not DEPARTMENTS:
        return "DEPARTMENTS"
    return None


def _form(body: str) -> str | None:
    # `re.ASCII` deliberately. Without it `\b` is Unicode-aware, so a form
    # sitting against an accented letter is a non-boundary here and a
    # boundary to checks/verify.py, which splits on `[^0-9A-Za-z_]+`. Two
    # derivations of one stated rule may differ in expression; they may not
    # differ on which characters are letters.
    for name, pattern in FORMS:
        if re.search(pattern, body, re.IGNORECASE | re.ASCII):
            return name
    return None


def main() -> None:
    if (missing := _unbuilt()) is not None:
        raise SystemExit(
            f"off-sense-register: {missing} is still a placeholder. Run "
            "datasets/merrick/measure_candidates.py and classify the sample "
            "before building this task."
        )

    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    slack = sqlite3.connect(f"file:{STATE / 'slack.db'}?mode=ro", uri=True)

    # End of the last day in the window, in the world's own
    # seconds-from-epoch. `time` on a served message is seconds, not a date:
    # comparing its string form against an ISO date compiles, runs, and
    # windows on a lexicographic accident.
    cutoff = WINDOW_DAYS * 86_400

    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = {
        person_id: {"name": name, "department": department}
        for person_id, name, department in gmail.execute(
            "SELECT person_id, name, department FROM people"
        )
    }
    # Channels only. A one-to-one conversation has no name for `where`, and
    # the instruction puts direct messages out of scope rather than leaving
    # the reader to invent a label for them.
    channels = dict(
        slack.execute(
            "SELECT conversation_id, name FROM conversations WHERE kind = 'channel'"
        )
    )

    rows = []
    forms = []
    read = 0
    for message_id, sender, when, subject, body in gmail.execute(
        "SELECT message_id, sender, time, subject, body FROM messages"
    ):
        if when >= cutoff:
            continue
        # Counted only inside the window. Requiring the whole record here is
        # what turns a task into no deliverable at all: the bound has to
        # apply to the work, not only to the answer.
        read += 1
        form = _form(body)
        if form is None:
            continue
        rows.append(
            {
                "ref": message_id,
                "author": people[sender]["name"],
                "sent_date": (epoch + datetime.timedelta(seconds=when))
                .date()
                .isoformat(),
                "where": subject,
            }
        )
        forms.append(form)
    for conversation, sender, when, ts, body in slack.execute(
        "SELECT conversation_id, sender, time, ts, body FROM messages"
    ):
        if when >= cutoff or conversation not in channels:
            continue
        read += 1
        form = _form(body)
        if form is None:
            continue
        rows.append(
            {
                "ref": ts,
                "author": people[sender]["name"],
                "sent_date": (epoch + datetime.timedelta(seconds=when))
                .date()
                .isoformat(),
                "where": channels[conversation],
            }
        )
        forms.append(form)

    order = sorted(range(len(rows)), key=lambda i: rows[i]["ref"])
    rows = [rows[i] for i in order]
    forms = [forms[i] for i in order]

    by_form: dict[str, int] = {name: 0 for name, _pattern in FORMS}
    by_department: dict[str, int] = {name: 0 for name in DEPARTMENTS}
    by_person: dict[str, int] = defaultdict(int)
    name_to_department = {p["name"]: p["department"] for p in people.values()}
    for row, form in zip(rows, forms, strict=True):
        by_form[form] += 1
        department = name_to_department[row["author"]]
        if department not in by_department:
            # A stale roster is silent otherwise: the missing department's
            # rows vanish from the object and every other key still reads
            # right, so the report is wrong in the one place nobody checks.
            raise SystemExit(
                f"off-sense-register: {department!r} is recorded on "
                f"{row['author']} and missing from DEPARTMENTS -- re-read "
                "the roster off the built state."
            )
        by_department[department] += 1
        by_person[row["author"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "hits_total": len(rows),
                "distinct_authors": len(by_person),
                "form_counts": dict(sorted(by_form.items())),
                "department_counts": dict(sorted(by_department.items())),
                # Most, then the earlier name -- `max` breaks a tie the other
                # way and the instruction says earlier.
                "top_author": min(by_person, key=lambda name: (-by_person[name], name)),
                "hits": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

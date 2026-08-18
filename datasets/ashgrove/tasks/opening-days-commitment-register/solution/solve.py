"""Reference solver: the opening days' commitment register.

The same seven forms as `commitment-register`, bounded to the firm's
first two working days -- 213 messages of the 1,585, 71 rows.

Bounded because the full register is unmeasurable below Opus: glm-5.2
times out on it and gpt-5.6-sol abandons it to subagents. Worth bounding
because these seven forms are the hardest rule in the suite for the tier
below -- glm scores 0.213 applying them in `commitment-follow-through`,
against 0.736 or better on everything else it finishes.

Original docstring follows.

Reference solver: every deadline promised in the body of a message.

The point of this task is that there is nothing to query. A commitment is
not a column, a flag, or a field anybody fills in — it is a sentence, and
the only way to the register is to read all of the traffic and resolve
what each sentence meant on the day it was written. Mail and chat both:
the firm makes as many promises to itself as to its clients.

Every rule is stated verbatim in the instruction, so the task measures
whether an agent can apply seven fixed patterns to fifteen hundred bodies
without missing any, not whether it can guess a grader's taste. The
resolution is deliberately mechanical: `by Friday` is the next Friday
strictly after the sent date whether or not the writer said "next",
because the firm's people do not use that word consistently and a rule
that tried to read their intent could not be graded.

One row per message and due date. A message that says `by Friday` twice
promised one thing; a message that says `by Friday` and `EOD` promised two.

A message is named the way its own system names it. Mail has
``msg-000001``. Slack has no such id on the wire — it addresses a message
by its timestamp — so a chat row is named by that timestamp, and the
author has to be resolved from a Slack user id through the directory.
Asking for the world's internal ``chm-`` id instead would be asking the
agent to guess a vocabulary no tool ever emits.
"""

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
# End of Tuesday 6 January 2026, the second working day.
CUTOFF = 2 * 86_400
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("opening_commitments.json")

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
WORD_DAYS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}
# "by April 15th" is the form `by <Month> <day>`; a bare \b after the
# digits drops every ordinal spelling. That defect certified 17 correct
# rows as model errors on the commitment register before anyone noticed,
# because the check that confirmed them used this same pattern.
PATTERNS = (
    ("weekday", r"\bby (?:this |next |)(monday|tuesday|wednesday|thursday|friday)\b"),
    # The firm writes "by end of week" 24 times and "by end of next week"
    # 10 times; it writes "by the end of the week" once. A rule that
    # required the articles admitted 1 of 35 end-of-week promises and
    # called the other 34 hallucinations -- twice, identically, which is
    # the tell for a task defect rather than a model one.
    #
    # No leading "by", for the same reason the day form does not require
    # one: `end of day` and `close of business` have always matched bare,
    # so `end of week` matching only after "by" was an inconsistency a
    # careful reader would trip on rather than a distinction worth making.
    # All three "end of X" families now behave alike.
    ("week", r"\bend of (?:the |this |next )?week\b|\beow\b"),
    ("month", r"\bend of (?:the |this |next )?month\b|\beom\b"),
    ("date", rf"\bby ({'|'.join(MONTHS)}) (\d{{1,2}})(?:st|nd|rd|th)?\b"),
    ("day", r"\b(?:eod|cob|end of day|close of business)\b"),
    ("within", r"\bwithin (\d+|a|two|three|five|ten) (?:business )?days?\b"),
    ("tomorrow", r"\bby tomorrow\b"),
)
FIRM = "the firm"


def _due(kind: str, match: re.Match, sent: datetime.date) -> datetime.date:
    if kind == "weekday":
        ahead = (WEEKDAYS.index(match.group(1).lower()) - sent.weekday()) % 7
        # Strictly after: a Friday message saying "by Friday" means the next.
        return sent + datetime.timedelta(days=ahead or 7)
    if kind == "week":
        return sent + datetime.timedelta(days=(4 - sent.weekday()) % 7)
    if kind == "month":
        first_next = (sent.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return first_next - datetime.timedelta(days=1)
    if kind == "date":
        return datetime.date(sent.year, MONTHS.index(match.group(1).lower()) + 1,
                             int(match.group(2)))
    if kind == "day":
        return sent
    if kind == "within":
        count = match.group(1).lower()
        return sent + datetime.timedelta(
            days=int(count) if count.isdigit() else WORD_DAYS[count]
        )
    return sent + datetime.timedelta(days=1)


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    slack = sqlite3.connect(f"file:{STATE / 'slack.db'}?mode=ro", uri=True)
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    # The databases date a message in seconds from the world's epoch, which
    # they carry; the tools serve the same instant as a timestamp.
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )

    people = {
        row[0]: {"name": row[1], "domain": row[2].split("@")[-1], "affiliation": row[3]}
        for row in gmail.execute(
            "SELECT person_id, name, email_address, affiliation FROM people"
        )
    }
    # An organisation is matched to a mail domain by its own name with the
    # punctuation taken out: "Shaw & Associates" -> shawassociates.example.
    organisations = {
        "".join(c for c in name.lower() if c.isalnum()): name
        for (name,) in clio.execute("SELECT name FROM organizations")
    }
    channels = dict(
        slack.execute("SELECT conversation_id, name FROM conversations")
    )

    parties: dict[str, set[str]] = defaultdict(set)
    for message_id, person in gmail.execute(
        "SELECT message_id, person_id FROM recipients"
    ):
        parties[message_id].add(person)

    rows: dict[tuple[str, str], dict] = {}
    read = 0

    def collect(ref: str, sender: str, when: int, body: str, made_to: str) -> None:
        if when >= CUTOFF:
            return
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        for kind, pattern in PATTERNS:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                due = _due(kind, match, sent)
                # Keyed on the pair, so a body that promises the same date
                # twice contributes one row and not two.
                rows[(ref, due.isoformat())] = {
                    "ref": ref,
                    "due_date": due.isoformat(),
                    "author": people[sender]["name"],
                    "sent_date": sent.isoformat(),
                    "made_to": made_to,
                }

    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        if when < CUTOFF:
            read += 1
        outside = sorted(
            {
                organisations.get(
                    people[person]["domain"].split(".")[0],
                    people[person]["domain"],
                )
                for person in parties[message_id] | {sender}
                if people.get(person, {}).get("affiliation") == "external"
            }
        )
        collect(message_id, sender, when, body, outside[0] if outside else FIRM)

    for conversation, sender, when, ts, body in slack.execute(
        "SELECT conversation_id, sender, time, ts, body FROM messages"
    ):
        if when < CUTOFF:
            read += 1
        # Slack names a message by its timestamp, which is what the surface
        # serves and therefore what the register must carry.
        collect(ts, sender, when, body, channels.get(conversation, conversation))

    register = [rows[key] for key in sorted(rows)]
    by_due: dict[str, int] = defaultdict(int)
    by_party: dict[str, int] = defaultdict(int)
    for row in register:
        by_due[row["due_date"]] += 1
        by_party[row["made_to"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "commitments_total": len(register),
                "messages_with_commitment": len({r["ref"] for r in register}),
                # Most, then the earlier date / earlier name -- `min` on a
                # negated count, because `max` breaks a tie the other way and
                # the instruction says earlier.
                "busiest_due_date": min(
                    by_due, key=lambda date: (-by_due[date], date)
                ),
                "top_made_to": min(
                    by_party, key=lambda name: (-by_party[name], name)
                ),
                "commitments": register,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

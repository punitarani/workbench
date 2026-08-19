"""Reference solver: work reported complete, in the one word that counts.

The register admits two words, `complete` and `completed`, and nothing
else. Seventy messages in this firm's traffic say `finished`, `wrapped up`,
`closed out`, `finalised`, `delivered` or `issued` and mean exactly the
same thing — and that is the point, and the difference from a register of
approvals.

"Agreed" is not "approved": they are different acts, so a reader keeps them
apart without effort and the rule costs nothing. "Finished" *is*
"completed". Excluding it is a decision about spelling rather than about
meaning, and it has to be made seventy times against everything the reader
knows the sentence says.
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("completion_claims.json")

# In this order: the first that matches names the row's form, so a message
# carrying two of them is still one approval with one name.
# Both spellings of one word and nothing else -- not inflections of it and
# not synonyms for it. `completes`, `completing` and `completion` are none
# of the two spellings the instruction names, and the corpus carries 56 of
# them; the instruction now says so outright rather than leaving a reader
# to infer it from "the word *complete*".
FORMS = (
    ("complete", r"\bcomplete\b"),
    ("completed", r"\bcompleted\b"),
)


def _form(body: str) -> str | None:
    for name, pattern in FORMS:
        if re.search(pattern, body, re.IGNORECASE):
            return name
    return None


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    slack = sqlite3.connect(f"file:{STATE / 'slack.db'}?mode=ro", uri=True)
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = {
        row[0]: {"name": row[1], "domain": row[2].split("@")[-1], "affiliation": row[3]}
        for row in gmail.execute(
            "SELECT person_id, name, email_address, affiliation FROM people"
        )
    }
    organisations = {
        "".join(c for c in name.lower() if c.isalnum()): name
        for (name,) in clio.execute("SELECT name FROM organizations")
    }
    channels = dict(slack.execute("SELECT conversation_id, name FROM conversations"))
    parties: dict[str, set[str]] = defaultdict(set)
    for message_id, person in gmail.execute(
        "SELECT message_id, person_id FROM recipients"
    ):
        parties[message_id].add(person)

    rows = []
    forms = []
    read = 0
    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        read += 1
        form = _form(body)
        if form is None:
            continue
        outside = sorted(
            {
                organisations.get(
                    people[p]["domain"].split(".")[0], people[p]["domain"]
                )
                for p in parties[message_id] | {sender}
                if people.get(p, {}).get("affiliation") == "external"
            }
        )
        rows.append(
            {
                "ref": message_id,
                "claimant": people[sender]["name"],
                "sent_date": (epoch + datetime.timedelta(seconds=when))
                .date()
                .isoformat(),
                "where": outside[0] if outside else "the firm",
            }
        )
        forms.append(form)
    for conversation, sender, when, ts, body in slack.execute(
        "SELECT conversation_id, sender, time, ts, body FROM messages"
    ):
        read += 1
        form = _form(body)
        if form is None:
            continue
        rows.append(
            {
                "ref": ts,
                "claimant": people[sender]["name"],
                "sent_date": (epoch + datetime.timedelta(seconds=when))
                .date()
                .isoformat(),
                "where": channels.get(conversation, conversation),
            }
        )
        forms.append(form)
    order = sorted(range(len(rows)), key=lambda i: rows[i]["ref"])
    rows = [rows[i] for i in order]
    forms = [forms[i] for i in order]
    # form_counts still needs the classification; the row no longer prints
    # it. Naming which of six words matched, per row, is a checklist handed
    # to the agent -- the same decomposition that made self-review-exposure
    # score 1.000 three times over.

    # Every listed form, including the two nobody used. Emitting only the
    # forms that occur would make "does a zero belong in the object?" a
    # judgement the instruction never settles, and an answer can be marked
    # wrong for guessing it either way.
    by_form: dict[str, int] = {name: 0 for name, _pattern in FORMS}
    by_person: dict[str, int] = defaultdict(int)
    for row, form in zip(rows, forms, strict=True):
        by_form[form] += 1
        by_person[row["claimant"]] += 1
    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "claims_total": len(rows),
                "distinct_claimants": len(by_person),
                "form_counts": dict(sorted(by_form.items())),
                # Most, then the earlier name -- `max` breaks a tie the
                # other way and the instruction says earlier.
                "top_claimant": min(
                    by_person, key=lambda name: (-by_person[name], name)
                ),
                "claims": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

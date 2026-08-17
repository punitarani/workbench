"""Show me the sentence, not the regex that agreed with itself.

    uv run python datasets/ashgrove/adjudicate.py msg-000104 1767661500.000003
    uv run python datasets/ashgrove/adjudicate.py --from-classify < misses.txt

Every disputed row on the two commitment tasks was "verified" by re-running
the solver's own pattern over the message it came from. That check cannot
fail: if the pattern is what put the row in the oracle, the pattern will
agree that the row belongs there, and it will agree just as confidently
about the rows it never produced. Seventeen correct rows were certified as
model errors that way, because `\\bby (month) (\\d{1,2})\\b` cannot see
`by April 15th` and neither could anything downstream of it.

So this deliberately does not know the rule. It casts a net far wider than
the seven forms — anything that looks remotely like a time promise — and
prints the sentence. The verdict is then read off English:

* the sentence carries one of the seven forms, and the oracle lacks the
  row  ->  **T**, the pattern is narrower than the prose it implements;
* the sentence carries nothing the rule admits, and the agent produced a
  row  ->  **M**, the agent invented a deadline;
* no sentence at all  ->  **M**, unless the body was never served, which
  is **E** and the reachability gate would have caught it.

The net is asserted to be a strict superset of the rule in
`tests/analysis/test_stated_rules_match_their_patterns.py`, which is the
only property that makes it useful: it may over-report freely, but it must
never miss something the rule would have matched.
"""

import argparse
import datetime
import re
import sqlite3
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[2] / "out" / "ashgrove" / "bundle" / "state"

# Deliberately promiscuous. Every one of these fires on things the register
# does not admit -- "sometime in March", "early next week", "asap" -- and
# that is the point: over-reporting costs a line of output, under-reporting
# costs a false certification.
NET = re.compile(
    r"""
      \bby\s+\w+                      # by Monday, by March, by then, by EOD
    | \bwithin\s+\w+                  # within five days, within the week
    | \b(?:eod|cob|eow|asap)\b
    | \bend\s+of\b | \bclose\s+of\b
    | \b(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday
        |saturday|sunday)\b
    | \b(?:january|february|march|april|may|june|july|august|september
        |october|november|december)\b
    | \b\d{1,2}(?:st|nd|rd|th)\b      # the 15th, standing alone
    | \b\d{4}-\d{2}-\d{2}\b
    | \bdue\b | \bdeadline\b | \bturn(?:around|\s+it)\b
    | \bnext\s+week\b | \bthis\s+week\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _epoch(db: sqlite3.Connection) -> datetime.datetime:
    return datetime.datetime.fromisoformat(
        dict(db.execute("SELECT key, value FROM meta"))["epoch"]
    )


def _open(name: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{BUNDLE / name}?mode=ro", uri=True)


def _bodies(refs: set[str]) -> dict[str, tuple[str, str, str]]:
    """ref -> (sent date, author, body), across both systems."""

    found: dict[str, tuple[str, str, str]] = {}

    gmail = _open("gmail.db")
    epoch = _epoch(gmail)
    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        if message_id in refs:
            sent = (epoch + datetime.timedelta(seconds=when)).date().isoformat()
            found[message_id] = (sent, names.get(sender, sender), body)

    slack = _open("slack.db")
    # Chat is named on the wire by its timestamp, so that is the ref a row
    # carries and the only handle a disputed row gives us.
    for ts, sender, when, body in slack.execute(
        "SELECT ts, sender, time, body FROM messages"
    ):
        if ts in refs:
            sent = (epoch + datetime.timedelta(seconds=when)).date().isoformat()
            found[ts] = (sent, names.get(sender, sender), body)

    return found


def show(refs: list[str]) -> int:
    wanted = {r.strip() for r in refs if r.strip()}
    found = _bodies(wanted)

    for ref in sorted(wanted):
        if ref not in found:
            # Not served at all is the environment's problem, not the
            # model's, and worth saying loudly rather than reporting as an
            # empty body.
            print(f"\n{ref}  ** NOT IN THE RECORD -- E, or a hallucinated ref **")
            continue
        sent, author, body = found[ref]
        print(f"\n{ref}  sent {sent}  by {author}")
        hits = [
            sentence.strip()
            for sentence in _SENTENCE.split(body)
            if NET.search(sentence)
        ]
        if not hits:
            print("    (nothing time-shaped anywhere in the body)")
        for sentence in hits:
            print(f"    | {sentence}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="*", help="message ids and/or slack timestamps")
    parser.add_argument(
        "--from-classify",
        action="store_true",
        help="read refs from stdin, one per line or as classify_misses tuples",
    )
    args = parser.parse_args()

    refs = list(args.refs)
    if args.from_classify:
        # classify_misses prints row keys as ('msg-000104', '2026-04-15').
        refs += re.findall(r"[\w.-]+", sys.stdin.read())
    if not refs:
        parser.error("nothing to adjudicate")
    return show(refs)


if __name__ == "__main__":
    raise SystemExit(main())

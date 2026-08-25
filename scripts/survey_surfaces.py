"""Find, by measurement, which surfaces can host a task that measures.

    uv run python scripts/survey_surfaces.py --state out/merrick/bundle/state

**Why this is a tool and not a judgement.** Five registers were built over
one corpus before it was clear what separates the one that measures a
frontier tier from the four that do not. It is not corpus size, not
arithmetic, and not the subtlety of the rule: the same five-condition
attachment rule scores 1.000 on mail and 0.766 on meeting transcripts.

It is whether the **grouping key** is a field or a derivation.

    mail      group by `sender`  -- a column. Take the max. Done.
    meetings  group by series    -- a title on 3+ days, 8 of 52, 44
                                    one-offs discarded. Compute it first,
                                    and an error merges or drops a GROUP.

Row-F1 is sensitive to the row SET, so a derived key turns a small
reasoning error into a lost row while a column never can.

So this prints, per surface and per candidate grouping, the four numbers
that decide whether a task built on it can land in band:

* **derived** — whether the grouping has to be computed from the corpus or
  can be read off a column. A column is a warning on its own.
* **groups / one-offs** — how much the grouping discards. The discarding is
  where the error lives: `live-commitment-register` keeps 8 of 52 titles.
* **rows per owner** — 1.00 means the row set is "enumerate the people" and
  only the value is ever at stake. 1.17 was enough to matter.
* **repeat rate** — the share of groups holding more than one item, which
  is what supersession needs. Mail is 2% inside a thread and 0% inside a
  subject: this firm opens a new thread rather than re-promising in an old
  one, so a register keyed there has nothing to supersede and every row
  still looks right.

A surface that scores well on all four is worth building on. One that does
not is worth knowing about before a sweep, not after four.

**These four numbers are necessary and not sufficient, and the gap has a
name: they say nothing about whether the KEY CAN BE DERIVED.**

Measured on merrick, a register keyed by (person, matter) surveys better
than the task that works -- 29 groups, 16 owners, rows per owner 1.81
against 1.17, repeat 34%. Every number says build it. It is ungradable,
because the matter a promise concerns cannot be recovered:

* People name matters the way people do -- "Sable Ridge", "Kestrel",
  "Oseman" -- and those strings do not appear in the firm's own matter
  list, which calls them by client and description.
* A turn covers several matters. One turn discussing Sable Ridge keyed to
  a matter called "Sandhurst 9:15 Status Call Recap" because the only word
  the matter list recognised anywhere in it was `Status`.
* Only 1 admitted commitment in 35 names a matter in the same CLAUSE as
  the promise. Loosen it to the same turn and the key stops being about
  the promise at all.

This is the anchor limit in a second family: a key component the model
cannot reliably derive is one the ORACLE cannot reliably derive either.
The survey will not tell you that. Before building on a derived grouping,
print the derivation's output beside the source for twenty rows and read
them -- the wrong ones are obvious in seconds and invisible in aggregate.

**Run it with the rule the task will grade, not a proxy for it.** `--rule`
takes a module exposing `commitment_in`, and it matters more than it looks:
under the loose default pattern this reported gmail-by-subject at 39%
repeat, a surface worth building on. Under the real attachment rule the
same grouping is 0% -- 537 messages carry an `I'll` somewhere, and 61 carry
a promise the rule admits. A survey run on a proxy flatters every surface
where the graded rule is stricter than the proxy, which is all of them.

The regex default stays for surveying a corpus before a rule exists. It is
a first look, and the numbers it prints are upper bounds.
"""

import argparse
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

# The default item: a first-person commitment. Deliberately looser than the
# graded rule -- this is a survey of where items live, not a key.
DEFAULT_PATTERN = r"\bI'll\b|\bI will\b"

# A grouping keeps a group when it holds at least this many items, mirroring
# `STANDING_SERIES_MINIMUM`. Below it a "series" is a one-off wearing the
# word.
SERIES_MINIMUM = 3


def _norm(value: str) -> str:
    """Subject lines, with the reply markers taken off."""

    return re.sub(r"^(re|fwd)\s*:\s*", "", (value or "").strip(), flags=re.I).casefold()


# Per surface: the table, the text column, the owner column, and the
# groupings worth trying. `derived` says whether the grouping is a column
# read straight off the row or something the corpus has to be searched for.
SURFACES: dict[str, dict] = {
    "meetings": {
        "table": "utterances",
        "text": "text",
        "owner": "speaker",
        "join": (
            "SELECT u.speaker, u.text, m.meeting_id, m.title, m.started "
            "FROM utterances u JOIN meetings m ON m.meeting_id = u.meeting_id"
        ),
        "groupings": {
            "meeting_id": (False, lambda row: row["meeting_id"]),
            "title (a standing series)": (True, lambda row: row["title"]),
        },
    },
    "gmail": {
        "table": "messages",
        "text": "body",
        "owner": "sender",
        "join": "SELECT sender, body, thread_id, subject FROM messages",
        "groupings": {
            "thread_id": (False, lambda row: row["thread_id"]),
            "subject (normalised)": (True, lambda row: _norm(row["subject"])),
        },
    },
    "slack": {
        "table": "messages",
        "text": "body",
        "owner": "sender",
        "join": "SELECT sender, body, conversation_id FROM messages",
        "groupings": {
            "conversation_id": (False, lambda row: row["conversation_id"]),
        },
    },
}


def survey(state: Path, pattern: str, rule: str | None) -> None:
    if rule:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_rule", rule)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        admits = lambda text: module.commitment_in(text or "") is not None  # noqa: E731
        print(f"  item = a promise the rule in {rule} admits\n")
    else:
        matcher = re.compile(pattern, re.IGNORECASE)
        admits = lambda text: bool(matcher.search(text or ""))  # noqa: E731
        print(
            f"  item = a body matching {pattern!r}\n"
            "  !! this is a PROXY. Numbers below are upper bounds; pass --rule\n"
            "     to measure what the task will actually grade.\n"
        )
    header = (
        f"  {'surface / grouping':44s} {'derived':>7s} {'items':>6s} "
        f"{'groups':>7s} {'kept':>5s} {'r/owner':>8s} {'repeat':>7s}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, spec in SURFACES.items():
        path = state / f"{name}.db"
        if not path.is_file():
            continue
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(spec["join"]).fetchall()
        except sqlite3.Error as exc:
            print(f"  {name}: {exc}")
            continue
        items = [row for row in rows if admits(row[spec["text"]])]
        for label, (derived, keyfn) in spec["groupings"].items():
            counts: Counter = Counter()
            for row in rows:
                counts[keyfn(row)] += 1
            kept = {key for key, n in counts.items() if n >= SERIES_MINIMUM}
            held = defaultdict(list)
            for row in items:
                key = keyfn(row)
                if key in kept:
                    held[(row[spec["owner"]], key)].append(row)
            owners = {owner for owner, _ in held}
            per_owner = len(held) / len(owners) if owners else 0.0
            repeat = (
                sum(1 for v in held.values() if len(v) > 1) / len(held) if held else 0.0
            )
            print(
                f"  {name + ' / ' + label:44s} {'yes' if derived else 'NO':>7s} "
                f"{len(items):>6d} {len(counts):>7d} {len(kept):>5d} "
                f"{per_owner:>8.2f} {repeat:>6.0%}"
            )
    print(
        "\n  A grouping that is NOT derived is a warning on its own: the agent\n"
        "  reads the column and the row set costs it nothing. `r/owner` at 1.00\n"
        "  says the same thing a second way. `repeat` is what supersession has\n"
        "  to work with -- at 0% a register keyed there has nothing to supersede\n"
        "  and every row still looks right."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument(
        "--rule",
        default=None,
        help="path to a module exposing commitment_in(text); use the rule "
        "the task grades, because a proxy flatters every surface",
    )
    args = parser.parse_args(argv)
    if not args.state.is_dir():
        raise SystemExit(f"no state directory at {args.state}")
    survey(args.state, args.pattern, args.rule)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

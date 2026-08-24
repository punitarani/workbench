"""Everything the off-sense register's brief has to state about one family.

    uv run python datasets/merrick/measure_word_family.py file filed [--days N]

`measure_candidates.py` answers which families the corpus could carry.
This answers what the brief must then *say* about the one chosen, because
that brief asks for five things by name and every one of them is a count
somebody would otherwise guess:

* the excluded inflections, **with the count of each**, in the manner of
  "*completion* alone appears fifty times";
* the synonyms the firm's traffic actually uses, and how many messages
  carry one and never carry an admitted form;
* two real examples, one squarely on the term's own subject and one
  plainly off it;
* how many rows the window produces, and how many messages a reader has
  to open to find them;
* the hyphen case, which the brief settles explicitly — `re-filed` is two
  words and carries the form, `refiled` is one word and does not.

That last one is the trap most worth measuring rather than assuming. It
is a rule the brief states plainly and a reader is very likely to apply
in only one direction.

Nothing here decides anything. It prints what the corpus holds so a
person can write a brief that is true of it.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

# Read from the same place every other measurement in this dataset reads,
# so a stale bundle cannot answer one question and not another.
STATE = Path(os.environ.get("WORKBENCH_STATE", "out/merrick/bundle/state"))

# Endings a law firm actually writes. Deliberately a list rather than a
# stemmer: the brief admits exactly two forms and excludes every other,
# so what matters is which *specific* other forms the reader will meet.
_ENDINGS = ("", "d", "ed", "s", "es", "ing", "ings", "ment", "ments", "ation", "ations")


def _inflections(stem: str) -> list[str]:
    """Every form of `stem` a reader might meet, spelled as English spells it.

    Concatenating endings is not enough, and the gap is not academic. For
    the stem `file` it produces `fileing`, which occurs nowhere, and never
    produces `filing`, which occurs in **407 messages** — the single
    largest over-admission trap in the corpus. Measured with the naive
    list, the same window reported one excluded inflection carrying one
    message, and a brief written from that would have told the agent the
    trap was negligible.

    So a stem ending in a silent `e` drops it before a vowel-initial
    ending, which is the rule that makes `file` -> `filing` and
    `resolve` -> `resolving`.
    """

    forms = {stem + ending for ending in _ENDINGS}
    if stem.endswith("e"):
        forms |= {
            stem[:-1] + ending for ending in _ENDINGS if ending and ending[0] in "aeiou"
        }
    return sorted(forms)


def _bodies(surface: str, window_end: int | None) -> list[tuple[str, str]]:
    path = STATE / f"{surface}.db"
    if not path.is_file():
        return []
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    where = "WHERE time <= ?" if window_end is not None else ""
    args = (window_end,) if window_end is not None else ()
    rows = connection.execute(f"SELECT body FROM messages {where}", args).fetchall()
    connection.close()
    return [(surface, row[0] or "") for row in rows]


def _word(form: str) -> re.Pattern[str]:
    """The brief's own boundary rule: letters, digits and the underscore
    continue a word, every other character ends one. That is `\\b`, and it
    is why `re-filed` carries `filed` and `refiled` does not."""

    return re.compile(rf"\b{re.escape(form)}\b", re.IGNORECASE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("form_a")
    parser.add_argument("form_b")
    parser.add_argument("--stem", default=None, help="defaults to form_a")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--synonym", action="append", default=[])
    args = parser.parse_args(argv)

    window_end = args.days * 86_400 - 1 if args.days else None
    messages = _bodies("gmail", window_end) + _bodies("slack", window_end)
    if not messages:
        raise SystemExit(f"no messages under {STATE}; build the bundle first")
    bodies = [body for _, body in messages]

    rx_a, rx_b = _word(args.form_a), _word(args.form_b)
    hits = [b for b in bodies if rx_a.search(b) or rx_b.search(b)]
    scope = f"first {args.days} days" if args.days else "whole record"
    print(f"corpus: {len(bodies)} messages ({scope})")
    print(f"admitted forms {args.form_a!r} / {args.form_b!r}: {len(hits)} rows")
    only_a = sum(1 for b in hits if rx_a.search(b) and not rx_b.search(b))
    only_b = sum(1 for b in hits if rx_b.search(b) and not rx_a.search(b))
    print(
        f"  {args.form_a}-only {only_a}, {args.form_b}-only {only_b}, "
        f"both {len(hits) - only_a - only_b}"
    )
    print(f"  a reader opens {len(bodies)} messages to find {len(hits)}")

    # The verdict, rather than four numbers and a hope. Each threshold is
    # a failure this dataset has already had:
    #
    # * a family whose second spelling appeared in *one* message out of
    #   1,585 — the register admits two forms and the corpus carries one,
    #   so `form_counts` has a key that is always zero and the rule's
    #   second half is never exercised;
    # * a window with too few rows to distinguish a reader from a guesser;
    # * a window whose reading load is so large that what is being
    #   measured is stamina rather than the rule.
    minority = min(only_a, only_b) + (len(hits) - only_a - only_b)
    verdicts = []
    if len(hits) < 12:
        verdicts.append(f"only {len(hits)} rows, under the 12-row floor")
    if minority < 5 or (hits and minority / len(hits) < 0.15):
        verdicts.append(
            f"the minority form appears in {minority} of {len(hits)} rows — "
            "the register would admit a second spelling the corpus barely writes"
        )
    if len(bodies) > 400:
        verdicts.append(
            f"{len(bodies)} messages to read, against the ~213 the in-band "
            "precedent settled on — that is stamina, not the rule"
        )
    print("  VERDICT: " + ("; ".join(verdicts) if verdicts else "usable"))

    stem = args.stem or args.form_a
    print("\nexcluded inflections — each one an over-admission trap")
    for form in _inflections(stem):
        if form.lower() in {args.form_a.lower(), args.form_b.lower()}:
            continue
        rx = _word(form)
        carrying = [b for b in bodies if rx.search(b)]
        if not carrying:
            continue
        alone = sum(1 for b in carrying if not (rx_a.search(b) or rx_b.search(b)))
        print(
            f"  {form:14s} {len(carrying):4d} messages, {alone:4d} carrying no "
            "admitted form (a stem match would add these)"
        )

    print("\nthe hyphen rule, which cuts both ways")
    for form in (args.form_a, args.form_b):
        hyphenated = re.compile(rf"\w+-{re.escape(form)}\b", re.I)
        joined = re.compile(rf"\b\w+{re.escape(form)}\b", re.I)
        h = [m.group(0) for b in bodies for m in hyphenated.finditer(b)]
        j = [
            m.group(0)
            for b in bodies
            for m in joined.finditer(b)
            if not m.group(0).lower().startswith(form.lower())
        ]
        print(
            f"  hyphenated, carrying {form!r} (HITS): "
            f"{len(h)} {Counter(h).most_common(4)}"
        )
        print(
            f"  longer single words containing {form!r} (NOT hits): "
            f"{len(j)} {Counter(j).most_common(4)}"
        )

    if args.synonym:
        print("\nsynonyms — messages carrying one and never an admitted form")
        for word in args.synonym:
            rx = _word(word)
            alone = [
                b
                for b in bodies
                if rx.search(b) and not (rx_a.search(b) or rx_b.search(b))
            ]
            print(f"  {word:14s} {len(alone):4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

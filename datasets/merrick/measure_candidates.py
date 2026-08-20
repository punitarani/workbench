"""What the corpus will actually support, measured before a task is built.

    uv run python datasets/merrick/measure_candidates.py [--state DIR] [--days N]

Every task shape below has one number that decides whether it is worth
building, and every one of those numbers has been guessed wrong at least
once in this tree. Guessing costs a full build plus a rollout sweep;
asking costs a query.

Three screens, one per shape:

**Word family** — for a register admitting one word in two spellings. The
decisive number is the *off-sense share* of the admitted form: how often
it appears meaning something other than the register's own idea. That is
what the weaker tiers miss, and it cannot be counted mechanically, so
this prints a sample to classify. Liveness and minority share are printed
too, as hygiene: one family that read perfectly on paper had its second
spelling in a single message out of 1,585, and another's in none at all.

**Date-form density** — for a promise-and-deadline register. What share of
messages carry a relative-date form at all. Too thin and there are not
twelve rows; too rich and the window has to shrink.

**Two-form messages** — for the compositional shape, where one message
names two forms resolving to *different* dates. This was the mechanism
behind the hardest measured date task: every trial found the first form
and two of nine found the second. It is rare, and mail-weighted, so
whether the task is mail-only is a decision the count makes rather than
the author.

Nothing here writes a task. It says which tasks the world can carry.
"""

import argparse
import datetime
import os
import re
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from analysis.form_families import Family, measure_family, screen

REPO = Path(__file__).resolve().parents[2]
DEFAULT_STATE = REPO / "out" / "merrick" / "bundle" / "state"

# Candidates a law firm's traffic might carry. Deliberately more than will
# survive: the point is to be told which are dead, and two of the most
# plausible-sounding families in the reference corpus were.
CANDIDATES: tuple[Family, ...] = (
    Family(
        "complete",
        ("complete", "completed"),
        ("completion", "completes", "completing"),
    ),
    Family("confirm", ("confirm", "confirmed"), ("confirmation", "confirms")),
    Family("serve", ("serve", "served"), ("service", "services", "serving")),
    Family("file", ("file", "filed"), ("filing", "filings", "files")),
    Family("execute", ("execute", "executed"), ("execution", "executes")),
    Family("produce", ("produce", "produced"), ("production", "produces")),
    Family("waive", ("waive", "waived"), ("waiver", "waivers", "waiving")),
    Family("retain", ("retain", "retained"), ("retainer", "retention")),
    Family("resolve", ("resolve", "resolved"), ("resolution", "resolves")),
    Family("advise", ("advise", "advised"), ("advice", "advisory", "advising")),
    Family("agree", ("agree", "agreed"), ("agreement", "agreements", "agrees")),
    Family("review", ("review", "reviewed"), ("reviewing", "reviews")),
)

# The seven forms the in-band date task admits, transcribed from the
# instruction the agent is graded against rather than from any solver.
_DATE_FORMS: tuple[tuple[str, str], ...] = (
    ("by weekday", r"by\s+(?:this\s+|next\s+)?(mon|tues|wednes|thurs|fri)day"),
    ("end of week", r"(?:by\s+)?(?:the\s+|this\s+|next\s+)?(?:end of week|eow)"),
    ("end of month", r"(?:by\s+)?(?:the\s+|this\s+|next\s+)?(?:end of month|eom)"),
    (
        "by month day",
        r"by\s+(?:january|february|march|april|may|june|july|august|september"
        r"|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?",
    ),
    ("end of day", r"\b(?:eod|cob|end of day|close of business)\b"),
    (
        "within N days",
        r"within\s+(?:\d+|a|two|three|five|ten)\s+(?:business\s+)?days?",
    ),
    ("by tomorrow", r"by\s+tomorrow"),
)


def _bodies(state: Path, horizon_seconds: int | None) -> tuple[list[str], list[str]]:
    """Mail and chat bodies, optionally only those sent within the window.

    ``time`` on a served message is **seconds since the world's epoch**,
    not a date. Comparing its string form against an ISO date compiles,
    runs, and windows on nothing: `"48900" <= "2026-01-09"` is a
    lexicographic accident. It cut a 268-message corpus to 46 and reported
    that as the window — worse than not filtering at all, because
    `screen()` was then told the report was windowed and checked the row
    floor against a number the filter had invented.
    """

    out = []
    for name in ("gmail.db", "slack.db"):
        path = state / name
        if not path.is_file():
            out.append([])
            continue
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = list(conn.execute("SELECT body, time FROM messages"))
        if horizon_seconds is not None:
            rows = [r for r in rows if int(r[1]) < horizon_seconds]
        out.append([r[0] for r in rows if r[0]])
    return out[0], out[1]


def _date_density(bodies: list[str]) -> tuple[int, int, Counter]:
    """Messages with at least one form, with at least two, and per-form counts."""

    patterns = [(name, re.compile(rx, re.I)) for name, rx in _DATE_FORMS]
    per_form: Counter = Counter()
    at_least_one = at_least_two = 0
    for body in bodies:
        hits = 0
        for name, pattern in patterns:
            found = len(pattern.findall(body))
            if found:
                per_form[name] += 1
                hits += found
        if hits >= 1:
            at_least_one += 1
        if hits >= 2:
            at_least_two += 1
    return at_least_one, at_least_two, per_form


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # `WORKBENCH_STATE` is how every other file in this dataset finds the
    # served world -- eleven of them -- and this script alone defaulted to
    # the committed bundle. Passing the env var did nothing, so a screen run
    # against a fresh projection silently measured a bundle built forty-five
    # recorded days earlier and returned numbers that looked entirely
    # plausible because they were: they were last month's answer.
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ["WORKBENCH_STATE"])
        if os.environ.get("WORKBENCH_STATE")
        else DEFAULT_STATE,
    )
    parser.add_argument(
        "--epoch", default="2026-01-05", help="first day of the recorded window"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="only messages within this many calendar days of the epoch",
    )
    parser.add_argument("--sample", type=int, default=12)
    args = parser.parse_args(argv)

    if not args.state.is_dir():
        parser.error(f"no served state at {args.state} — build the bundle first")

    cutoff = horizon = None
    if args.days is not None:
        # Sim-seconds, because that is what the served rows carry.
        horizon = args.days * 86_400
        cutoff = (
            date.fromisoformat(args.epoch) + timedelta(days=args.days - 1)
        ).isoformat()
    if args.days is None:
        print(
            "note: no --days, so this measures the whole corpus. The row "
            "floor is calibrated in the rows a task grades, so screen a "
            "window before believing a verdict.\n"
        )
    mail, chat = _bodies(args.state, horizon)
    bodies = mail + chat
    # Say which state was read and how fresh it is. A screen that prints only
    # its findings cannot be told apart from the same screen run last month.
    newest = max(
        (path.stat().st_mtime for path in args.state.glob("*.db")), default=0.0
    )
    print(
        f"state: {args.state} "
        f"(last built {datetime.datetime.fromtimestamp(newest):%Y-%m-%d %H:%M})"
        if newest
        else f"state: {args.state} (no databases found)"
    )

    window = f" through {cutoff}" if cutoff else ""
    print(f"corpus{window}: {len(mail)} mail + {len(chat)} chat = {len(bodies)}\n")
    if not bodies:
        print("nothing to measure yet.")
        return 0

    print("== word families (for a literalism register) ==")
    print(f"{'family':10s} {'msgs':>5s} {'occ':>5s} {'minority':>9s}  blocking")
    viable = []
    for family in CANDIDATES:
        report = measure_family(bodies, family, sample=args.sample)
        problems = screen(report, windowed=args.days is not None)
        # The off-sense screen always blocks until a human reads the
        # sample, so a family is "viable so far" when nothing else blocks.
        mechanical = [p for p in problems if "off-sense" not in p]
        verdict = (
            mechanical[0][:52] if mechanical else "clears hygiene — read the sample"
        )
        print(
            f"{report.name:10s} {report.messages:5d} {report.occurrences:5d} "
            f"{report.minority_share:8.1%}  {verdict}"
        )
        if not mechanical:
            viable.append(report)

    for report in viable:
        print(f"\n-- sample: {report.name} (classify on-sense vs off-sense) --")
        for window_text in report.samples:
            print(f"   ... {window_text[:150]}")

    print("\n== date forms (for a promise-and-deadline register) ==")
    for label, subset in (("mail", mail), ("chat", chat)):
        one, two, per_form = _date_density(subset)
        total = max(len(subset), 1)
        print(
            f"  {label:5s} {one:5d}/{len(subset)} carry >=1 form ({one / total:.1%}); "
            f"{two} carry >=2"
        )
        if per_form:
            top = ", ".join(f"{k}={v}" for k, v in per_form.most_common(4))
            print(f"        {top}")

    print(
        "\nFloors: >=20 messages and >=20% minority for a family; >=12 messages\n"
        "with two forms for the compositional shape. Off-sense share >=60% is\n"
        "the one that decides, and only a person reading the sample can set it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

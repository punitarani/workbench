"""Do this world's surfaces describe the same firm?

    uv run python scripts/coherence.py --state out/merrick/bundle/state

A firm's busiest matter is busy everywhere. The person carrying the most
work bills the most hours, sends the most mail, talks the most in meetings
and touches the most documents. The volumes differ; the ORDERING does not.

When the ordering disagrees, the surfaces were generated independently and
the world is a set of unrelated logs wearing one name.

**One existing band already asks this**, and an earlier version of this
docstring claimed nothing did. `cross.person_volume_spearman` has a floor
of 0.45 and reads -0.30 on the delegation world; it has been failing, in a
report that fails 39 of 91 bands and prints them all. That is the more
useful finding: the check existed and was drowned.

So what this adds is not the question but an answer a reader can act on.
The band gives one number over one aggregate. This names WHICH PAIR
disagrees -- documents~slack at +0.747 while mail~slack sits at -0.647
locates the defect in mail and nowhere else -- and, more importantly,
refuses to correlate against a surface that has no ordering at all, which
is what produced five confident inversions against a Gini of 0.059.

**What it cost to not have this.** merrick shipped with billing hours and
mail volume per person at Spearman -0.526: the people who bill the most
send the fewest emails. Six months of recording, four surfaces, and no gate
anywhere had an opinion about it. It was found by hand, late, while
answering a question about whether the environment was saleable.

**Why rank correlation and not counts.** Volumes legitimately differ by
orders of magnitude between surfaces -- 21,590 time entries against 1,399
emails -- and a partner may write few but long mails. What must hold is
that the same people and matters sit near the top of each list. Spearman
asks exactly that and nothing more.

**Reading the output.** A pair below the floor is not automatically a
defect: two surfaces can be genuinely unrelated in a real institution (a
paralegal files many documents and attends no meetings). A NEGATIVE
correlation is different, and is the finding this exists for -- it says the
generator inverted the relationship, which no institution does.

The exit code is the verdict: 0 coherent, 1 not.
"""

import argparse
import json
import sqlite3
import statistics
import sys
from pathlib import Path

# Where each surface records "this person did a unit of work", and what
# ONE UNIT IS. A surface with no such column cannot take part, and says so
# rather than being silently dropped -- a pair that never runs looks
# identical to a pair that passed.
#
# The fourth element weights each row. It matters: counting timesheet ROWS
# on merrick gives a Gini of 0.011 and counting the SECONDS in them gives
# 0.059, because everybody files a similar number of entries and the
# entries differ in length. Rows measure filing habits; seconds measure
# work. The first version of this script counted rows and called billing
# five times flatter than it is.
PER_PERSON: dict[str, tuple[str, str, str, str | None]] = {
    "billing": ("clio.db", "activities", "person", "quantity_seconds"),
    "mail": ("gmail.db", "messages", "sender", None),
    "slack": ("slack.db", "messages", "sender", None),
    "meetings": ("meetings.db", "utterances", "speaker", None),
    "documents": ("imanage.db", "versions", "author", None),
}

# Below this a pair is reported as weak. Not a hard floor: two surfaces can
# be honestly unrelated. The hard rule is the sign.
WEAK = 0.35

# Below this Gini a surface has no ordering to speak of, and correlating
# against it reads noise as a finding.
#
# This check came second and it should have come first. The first version
# of this script reported NINE inverted pairs on merrick, and five of them
# were against `billing` -- where every person logs between 976 and 1083
# entries, a Gini of 0.011 and a max/min of 1.11. There is no busiest
# person in that surface to disagree about. The inversions were the sign of
# a coin flip, reported with three decimal places.
#
# A uniform surface is its own defect and a worse one than an inversion: a
# firm where everybody does exactly the same amount of work is not a firm,
# and no task keyed on "who is busiest" can be built on it at all. So it is
# reported separately and loudly rather than folded into the pair table.
#
# A real firm's billable hours by person run 0.25-0.45.
UNIFORM = 0.10


def _counts(
    state: Path, db: str, table: str, column: str, weight: str | None = None
) -> dict[str, float] | None:
    path = state / db
    if not path.is_file():
        return None
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            return None
        # A weight column that the schema does not have is a silent
        # downgrade to row counting, which is the measure this exists to
        # avoid. Refuse instead: a surface that cannot be measured the way
        # it was declared should say so.
        if weight is not None and weight not in columns:
            return None
        measure = f"SUM({weight})" if weight else "COUNT(*)"
        return {
            key: float(total or 0)
            for key, total in connection.execute(
                f"SELECT {column}, {measure} FROM {table} "  # noqa: S608
                f"WHERE {column} IS NOT NULL GROUP BY {column}"
            )
        }
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def gini(counts: dict[str, float]) -> float:
    """How unequally the work is spread across this surface's actors.

    Zero means everybody did the same amount, which makes the ranking
    arbitrary and every correlation against it meaningless.
    """

    values = sorted(counts.values())
    total = sum(values)
    if not values or not total:
        return 0.0
    weighted = sum((index + 1) * value for index, value in enumerate(values))
    return (2 * weighted) / (len(values) * total) - (len(values) + 1) / len(values)


def spearman(left: dict[str, float], right: dict[str, float]) -> tuple[float, int]:
    """Rank correlation over the union of both surfaces' actors.

    The UNION, not the intersection. A person who bills heavily and sends
    no mail at all is the strongest evidence of incoherence there is, and
    intersecting would drop exactly that person from the comparison.
    """

    actors = sorted(set(left) | set(right))
    if len(actors) < 4:
        return 0.0, len(actors)

    def ranked(counts: dict[str, int]) -> list[float]:
        # Ties share the average rank; without this a surface where half
        # the actors are absent (all zero, all tied) reports a correlation
        # driven by alphabetical order.
        order = sorted(actors, key=lambda a: -counts.get(a, 0))
        ranks: dict[str, float] = {}
        index = 0
        while index < len(order):
            stop = index
            while (
                stop + 1 < len(order)
                and counts.get(order[stop + 1], 0) == counts.get(order[index], 0)
            ):
                stop += 1
            shared = (index + stop) / 2
            for position in range(index, stop + 1):
                ranks[order[position]] = shared
            index = stop + 1
        return [ranks[a] for a in actors]

    a, b = ranked(left), ranked(right)
    mean_a, mean_b = statistics.fmean(a), statistics.fmean(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    spread = sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b)
    return (numerator / spread**0.5 if spread else 0.0), len(actors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--weak", type=float, default=WEAK)
    parser.add_argument("--uniform", type=float, default=UNIFORM)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    surfaces: dict[str, dict[str, float]] = {}
    absent: list[str] = []
    for name, (db, table, column, weight) in PER_PERSON.items():
        counts = _counts(args.state, db, table, column, weight)
        if counts:
            surfaces[name] = counts
        else:
            absent.append(name)

    print(f"=== surface coherence: {args.state} ===\n")
    spread = {name: gini(counts) for name, counts in surfaces.items()}
    uniform = sorted(n for n, g in spread.items() if g < args.uniform)
    print(f"  {'surface':10s} {'actors':>6s} {'gini':>6s} {'max/min':>8s}  busiest")
    for name in sorted(surfaces):
        counts = surfaces[name]
        values = counts.values()
        ratio = max(values) / min(values) if min(values) else float("inf")
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        listed = ", ".join(k.replace("per-", "") for k, _ in top)
        flag = "  FLAT" if name in uniform else ""
        print(
            f"  {name:10s} {len(counts):6d} {spread[name]:6.3f} {ratio:8.2f}  "
            f"{listed}{flag}"
        )
    if absent:
        print(f"\n  not comparable (no per-person column): {', '.join(absent)}")

    if uniform:
        print(
            f"\n  {len(uniform)} surface(s) are FLAT — every actor did the same "
            f"amount of work:"
        )
        for name in uniform:
            print(f"    {name} at gini {spread[name]:.3f}")
        print(
            "  A firm where everybody works exactly as much as everybody else "
            "is not a\n  firm. These have no ordering, so they are excluded "
            "from the pairs below --\n  correlating against them reads a coin "
            "flip as a finding."
        )

    print()
    names = sorted(n for n in surfaces if n not in uniform)
    inverted, weak, results = [], [], {}
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            rho, n = spearman(surfaces[left], surfaces[right])
            results[f"{left}~{right}"] = rho
            mark = "  "
            if rho < 0:
                mark = "!!"
                inverted.append((left, right, rho))
            elif rho < args.weak:
                mark = " ?"
                weak.append((left, right, rho))
            print(f"  {mark} spearman({left:10s}, {right:10s}) = {rho:+.3f}   n={n}")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")

    print()
    if uniform:
        print(
            f"  NOT COHERENT — {len(uniform)} surface(s) carry no workload "
            f"signal at all"
        )
        if inverted:
            print(f"  ...and {len(inverted)} of the remaining pairs are inverted")
        for left, right, rho in inverted:
            print(f"    {left} and {right} at {rho:+.3f}")
        return 1

    if inverted:
        print(f"  NOT COHERENT — {len(inverted)} inverted pair(s):")
        for left, right, rho in inverted:
            print(
                f"    {left} and {right} at {rho:+.3f}. The actors busiest in "
                f"{left} are the LEAST busy in {right}. No institution does "
                f"this; a generator that ignored one surface while writing "
                f"the other does."
            )
        for left, right, _ in weak:
            print(f"  also weak: {left} and {right}")
        return 1

    if weak:
        print(f"  coherent, with {len(weak)} weak pair(s) — read them:")
        for left, right, rho in weak:
            print(f"    {left} and {right} at {rho:+.3f}")
        print(
            "  Weak is a judgement call: two surfaces can be honestly "
            "unrelated. Inverted is not."
        )
    else:
        print("  COHERENT — every pair of surfaces ranks its actors alike")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

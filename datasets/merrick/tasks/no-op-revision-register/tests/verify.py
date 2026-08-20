"""Second derivation of the no-op register, read out of the brief.

An independent verifier exists so the answer key is derived twice. A
verifier that copies the solver's regexes reproduces the solver's bugs and
then certifies that the two agree, which is a check that cannot fail; two
published scores in this repo were certified exactly that way.

So this file shares no rule literal with `solve.py`. The admitted phrases
are **parsed out of `instruction.md`** -- the prose the agent is graded
against -- and matched with plain string containment rather than a second
regex. A brief that changes what it admits changes what this verifier
admits, in the same edit.

Zero shared code is still not enough on its own: two files can hardcode the
same reading of a spec and never disagree. `insists` is the guard. Every
assumption the arithmetic makes is asserted against the brief's text, so
flipping the brief fails here instead of passing quietly. That guard earned
its place on a sibling task, where an anchor straddled a line break, matched
nothing, and would have left the verifier checking an empty rule and
passing everything.
"""

import datetime
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from brief_boundary import (  # noqa: E402
    check_reported,
    stated_boundary,
)
from brief_pins import unchanged  # noqa: E402

TASK = Path(__file__).resolve().parents[1]
BRIEF = (TASK / "instruction.md").read_text(encoding="utf-8")


class BriefChanged(AssertionError):
    """The brief no longer says what this file's arithmetic assumes."""


def insists(condition: object, what: str) -> None:
    if not condition:
        raise BriefChanged(
            f"instruction.md no longer states: {what}. The verifier's "
            "arithmetic assumes it. Re-read the brief and this file together "
            "-- do not relax the assertion."
        )


def _admitted_phrases() -> list[str]:
    head = BRIEF.split("carries one of exactly these", 1)
    insists(len(head) == 2, "the sentence introducing the admitted phrases")
    body = head[1].split("Case does not matter", 1)[0]
    lines = [ln.strip() for ln in body.splitlines() if ln.startswith("    ")]
    found = [w.strip() for ln in lines for w in ln.split(",") if w.strip()]
    insists(found, "the admitted phrases as an indented, comma-separated block")
    return found


PHRASES = _admitted_phrases()

insists(len(PHRASES) == 6, f"six admitted phrases (found {len(PHRASES)})")
insists(
    "first version is its creation" in BRIEF,
    "a document's first version is a creation and never makes a row",
)
insists("not by UTC" in BRIEF, "dates are read in the firm's time zone, not UTC")
insists(
    "deliberately not symmetric" in BRIEF.replace("**", ""),
    "the phrase list is exact and asymmetric ON PURPOSE. A dry run found "
    "this one charitable model away from a five-row false-positive burst: "
    "the record carries `no edits were made`, `no edit was made` and `no "
    "edit made`, and a reader who repairs the apparent typo emits 15 rows "
    "for 10 -- F1 0.80 from second-guessing the author, not from misreading "
    "the rule",
)
insists(
    "There is no matter filter" in BRIEF,
    "every document is in scope. The framing paragraph once said revisions "
    "were 'filed and recorded against a matter', which reads as a membership "
    "condition the rule never states and the oracle never applies -- taking "
    "it as one drops the rate card and two firm-administration documents",
)
insists(
    "version's own id, exactly as iManage gives it" in BRIEF.replace("**", ""),
    "the row key is the served version id, not an internal document id -- an "
    "audit found the register keyed on `doc-000012`, which no tool emits, so "
    "a perfect answer would have scored zero on every row",
)
insists(
    "first version is its creation, not a revision, so" in BRIEF,
    "versions_read excludes first versions. Left unstated, a literal reading "
    "of the brief gave 133 where the oracle gives 86, and BOTH derivations "
    "silently shared the exclusion -- so the cross-check could never see it",
)
insists(
    "cosmetic only" in BRIEF and "typo fix" in BRIEF,
    "the trivial-revision wordings are named as NOT admitting a row",
)
# The brief names these as excluded. If one ever appears among the admitted
# phrases the rule has collapsed, and both files would collapse together.
for trap in ("only formatting", "typo fix", "minor cleanup", "cosmetic only"):
    insists(
        not any(trap in phrase.lower() for phrase in PHRASES),
        f"{trap!r} stays out of the admitted list",
    )


# Every `insists` above is a substring test, so none of them can see an
# exception ADDED to a rule -- the brief could gain "...unless the sender
# copied themselves" and each pinned sentence would still be present. An
# audit measured that blind spot at 17-of-18 and 12-of-16 unnoticed
# mutations on this dataset's older verifiers.
#
# The digest closes it: any edit to the rule section at all breaks this,
# including a pure addition. When it fires, re-read the section against
# the code below and confirm the second derivation still implements it
# before re-pinning -- do not paste the new value in to make it pass.
unchanged(BRIEF, "## What makes a row", "aa60c143b1eb57a1")


def admits(comment: str) -> bool:
    folded = " ".join(comment.lower().split())
    return any(" ".join(phrase.lower().split()) in folded for phrase in PHRASES)


def recompute(state: Path, window_days: int) -> dict:
    import datetime

    imanage = sqlite3.connect(f"file:{state / 'imanage.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(imanage.execute("SELECT key, value FROM meta"))["epoch"]
    )
    limit = window_days * 86_400
    who = dict(imanage.execute("SELECT person_id, name FROM people"))
    titled = dict(imanage.execute("SELECT document_id, name FROM documents"))
    # Independently: read the library and number off the profile columns and
    # rebuild the served id, rather than trusting the solver's formatting.
    numbered = {
        doc: f"LEGAL!{number}"
        for doc, number in imanage.execute(
            "SELECT document_id, document_number FROM documents"
        )
    }

    rows, read = [], 0
    for doc, number, author, comment, at in imanage.execute(
        "SELECT document_id, version, author, comment, time FROM versions"
    ):
        if at >= limit or number <= 1:
            continue
        read += 1
        if not admits(comment):
            continue
        rows.append(
            {
                "document_ref": f"{numbered[doc]}.{number}",
                "author": who.get(author, author),
                "revised_date": (epoch + datetime.timedelta(seconds=at))
                .date()
                .isoformat(),
                "document_name": titled.get(doc, ""),
            }
        )
    rows.sort(key=lambda r: r["document_ref"])
    return {"versions_read": read, "no_op_revisions": rows}


def boundary_agrees(oracle: dict) -> None:
    """The brief's stated boundary must be the one the oracle was built on.

    Nothing compared these. The verifier took its window from `argv`, the
    build supplied that from the solver's own constant, and the brief's
    boundary sentence -- the thing the agent actually reads and windows on --
    was never in the loop. A brief saying one date while the oracle was cut
    on another grades every row against a window nobody was told about, and
    every row-level comparison stays green because both derivations share the
    integer.

    Skipped while the task is staged: the boundary is still a «MEASURE»
    placeholder, so there is no date to disagree with. It arms itself the
    moment one is written.
    """

    if "«MEASURE" in BRIEF:
        return
    reported = str(oracle.get("window_end", ""))
    try:
        stated = datetime.date.fromisoformat(reported)
    except ValueError:
        raise BriefChanged(
            f"the oracle's window_end is {reported!r}, which is not a date"
        ) from None
    stated_boundary(BRIEF, stated, "## The window")
    check_reported(oracle, stated)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: verify.py <state-dir> <window-days> <oracle.json>")
        return 2
    mine = recompute(Path(sys.argv[1]), int(sys.argv[2]))
    theirs = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    boundary_agrees(theirs)
    ok = True
    if mine["versions_read"] != theirs.get("versions_read"):
        print(
            f"versions_read: {mine['versions_read']} vs {theirs.get('versions_read')}"
        )
        ok = False
    # Keyed on the served id alone. `LEGAL!12.3` already names the version,
    # which is why the separate `version` column was dropped -- and this line
    # went on reading it, so `main()` raised KeyError on every invocation
    # while `recompute()` and the brief pins were both exercised and both
    # fine. The build calls `main()`. Test the entry point, not the parts.
    left = {r["document_ref"]: r for r in mine["no_op_revisions"]}
    right = {r["document_ref"]: r for r in theirs.get("no_op_revisions", [])}
    for key in sorted(set(left) | set(right)):
        if key not in right:
            print(f"only the verifier admits {key}")
            ok = False
        elif key not in left:
            print(f"only the solver admits {key}")
            ok = False
        elif left[key] != right[key]:
            print(f"{key} differs: {left[key]} vs {right[key]}")
            ok = False
    print(
        f"{'agree' if ok else 'DISAGREE'}: "
        f"{len(left)} verifier rows, {len(right)} solver rows"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

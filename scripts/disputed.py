"""Build an adjudication file from a contested row, without hand-picking it.

    uv run python scripts/disputed.py --dataset merrick \
        --task live-commitment-register \
        --row "Fionnuala Doherty | Employment practice huddle | 2026-02-19" \
        --rival 2026-02-12 --out disputed.json

**Why this is a script.** The passage a disputed row rests on was picked by
hand four times, and the fourth was wrong: the speaker had TWO turns in the
cited meeting, the commitment was in the second, and the judges were handed
the first. They returned SPLIT on the strength of a passage that contained
no promise at all -- a confident verdict about evidence that was never the
evidence.

Nothing about that failure was visible in the verdict. The row was real,
the meeting was right, the date was right, and the quoted reasoning was
sound about the text it was given. Only re-reading the meeting caught it.

So the passage is taken from the key's own citation and the rule's own
verdict: the turn the key cites is the LAST turn in that meeting the rule
admits, which is what the solver's supersession picks, and the rival is
the latest turn in the same series that resolves to the value the trials
reported. Neither is chosen by a human reading a transcript.
"""

import argparse
import datetime as dt
import importlib.util
import json
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]


def _rule(dataset: str):
    spec = importlib.util.spec_from_file_location(
        "_promise_rule", REPO / "datasets" / dataset / "promise_rule.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tokens_in(rule, text: str) -> list[str]:
    """Every deadline form the text names, admitted or not."""

    found = []
    for pattern, token in rule._DEADLINE:
        if pattern.search(text or ""):
            found.append(token)
    return found


def _every_turn(connection, who: str, group: str, epoch, zone):
    """Each turn by `who` in series `group`, in the order they were said."""

    for row in connection.execute(
        "SELECT u.text, m.started FROM utterances u "
        "JOIN meetings m ON m.meeting_id = u.meeting_id "
        "WHERE u.speaker = ? AND m.title = ? ORDER BY m.started, u.position",
        (who, group),
    ):
        said = (epoch + dt.timedelta(seconds=row["started"])).astimezone(zone)
        yield said, None, row["text"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--row",
        required=True,
        help="exactly as diagnose.py prints it: 'owner | group | value'",
    )
    parser.add_argument(
        "--rival",
        default=None,
        help="the value the trials reported for the same key, if any. Without "
        "it the judges see only the key's own evidence, which is how a row "
        "wrong for a reason elsewhere survives adjudication",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    state = task_dir / "environment" / ".workbench" / "state" / "meetings.db"
    if not state.is_file():
        raise SystemExit(f"no served meetings at {state}")
    rule = _rule(args.dataset)

    owner, group, held = (part.strip() for part in args.row.split("|"))
    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    cited = [
        row
        for row in oracle["live"]
        if row["owner"] == owner and row["meeting"] == group and row["due"] == held
    ]
    if not cited:
        raise SystemExit(f"the oracle holds no row {args.row!r}")

    connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    epoch = dt.datetime.fromisoformat(meta["epoch"])
    zone = ZoneInfo(meta["timezone"])
    who = {
        name: person
        for person, name in connection.execute("SELECT person_id, name FROM people")
    }[owner]

    admitted = []
    for row in connection.execute(
        "SELECT u.meeting_id, u.position, u.text, m.started "
        "FROM utterances u JOIN meetings m ON m.meeting_id = u.meeting_id "
        "WHERE u.speaker = ? AND m.title = ? ORDER BY m.started, u.position",
        (who, group),
    ):
        token = rule.commitment_in(row["text"])
        if token is None:
            continue
        said = (epoch + dt.timedelta(seconds=row["started"])).astimezone(zone)
        admitted.append(
            (
                said,
                row["meeting_id"],
                row["text"],
                rule.due_date(said.date(), token).isoformat(),
            )
        )

    # The key's evidence: the LAST admitted turn of the cited meeting, which
    # is the one the solver's supersession keeps. Taking the first is the
    # error this script exists to make impossible.
    inside = [a for a in admitted if a[1] == cited[0]["meeting_id"]]
    if not inside:
        raise SystemExit(
            f"the rule admits nothing in {cited[0]['meeting_id']}, which the "
            "oracle cites. That is a finding about the key, not a bad argument"
        )
    said, _meeting, passage, due = inside[-1]
    item: dict = {
        "row": (
            f"owner {owner!r}, meeting series {group!r}, due {held}. This turn "
            f"was spoken on {said:%A} {said.date()} at {said:%H:%M} {zone}."
        ),
        "passage": passage,
    }
    if args.rival:
        matching = [a for a in admitted if a[3] == args.rival]
        rejected = False
        if not matching:
            # The rival usually comes from a turn the rule REFUSES -- that
            # is what a disagreement about a value normally is. Searching
            # only admitted turns made this the common case the tool could
            # not serve, and it refused with a message that read like a
            # finding: "the value did not come from this series' text". It
            # had, from a turn this rule declines to admit, and the judges
            # need to see exactly that turn to say who is right.
            matching = [
                (said, meeting, text, args.rival)
                for said, meeting, text in _every_turn(
                    connection, who, group, epoch, zone
                )
                if any(
                    rule.due_date(said.date(), token).isoformat() == args.rival
                    for token in _tokens_in(rule, text)
                )
            ]
            rejected = True
        if not matching:
            raise SystemExit(
                f"no turn in {group!r} by {owner} names a day resolving to "
                f"{args.rival}, admitted or not. The trials' value came from "
                "somewhere else entirely, and that is the finding"
            )
        rival_said, _m, rival_text, _d = matching[-1]
        item["alternate"] = {
            "value": args.rival,
            "note": (
                "the rule behind the key does NOT admit this turn"
                if rejected
                else "the rule admits this turn too"
            ),
            "passage": (
                f"Spoken on {rival_said:%A} {rival_said.date()} at "
                f"{rival_said:%H:%M} {zone}, in the same {group!r} series:"
                f"\n\n{rival_text}"
            ),
        }
    args.out.write_text(json.dumps([item], indent=2) + "\n")
    print(f"  key evidence : {said.date()} {' '.join(passage.split())[:110]}…")
    if args.rival:
        print(
            f"  rival        : {rival_said.date()} "
            f"{' '.join(rival_text.split())[:110]}…"
        )
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reference solver: the week-one tracker against the system of record.

Somebody typed the tracker up in week one and circulated it. The practice
systems kept moving. The job is to say, line by line, where the sheet no
longer holds — and that turns on three decisions the agent has to get
right before a single row can be, because each of them moves every row at
once.

**The engagement is named twice.** The sheet says ``tkt-000004``, the id
staff see. Clio serves ``00004-KestrelManufacturing`` and never emits the
other form. The bridge is the number they share.

**The status is worded twice.** The sheet says `In progress` where clio
says `In-progress`, and `Complete` where clio says `Closed`. Those are the
same state written two ways, not a change. `In progress` also covers
`Waiting-client`, so a move between those two is invisible on a sheet of
this kind and is not a finding.

**The hours mean "as at", not "now".** Every figure on the sheet is the
total to its own date. Comparing it with the total to date is the whole
exercise; comparing it with itself finds nothing.

Get any one of the three wrong and the answer is wrong everywhere at
once, which is exactly why this task exists: adding rows to a task never
moved a score here, and the arithmetic says it never could.
"""

import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
WORKSPACE = Path(os.environ.get("WORKBENCH_WORKSPACE", STATE.parent / "workspace"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tracker_reconciliation.json")

TRACKER = "engagement-tracker-week1.md"
# What the sheet's wording means in clio's vocabulary. Two clio states share
# one word, which is ordinary for a spreadsheet and has to be survived.
SPOKEN = {
    "not started": {"open"},
    "in progress": {"in-progress", "waiting-client"},
    "in review": {"review"},
    "complete": {"closed"},
}


def _find_tracker() -> Path:
    matches = sorted(WORKSPACE.rglob(TRACKER))
    if not matches:
        raise SystemExit(f"no {TRACKER} anywhere under {WORKSPACE}")
    return matches[0]


def _rows(text: str, header: str) -> list[list[str]]:
    """The pipe table under a heading, as lists of stripped cells."""

    out: list[list[str]] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("# "):
            in_section = header in line
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if cells[0] in {"Engagement"}:
            continue
        out.append(cells)
    return out


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    names = dict(clio.execute("SELECT person_id, name FROM people"))
    # Client engagements only: the tracker covers the client book, so time
    # on the firm's own projects was never meant to be on it and is not a
    # thing the sheet is missing.
    matters = {
        row[0]: {"display": row[1], "status": row[2]}
        for row in clio.execute(
            "SELECT ticket_id, display_number, status FROM matters "
            "WHERE client_org IS NOT NULL"
        )
    }
    minutes: dict[tuple[str, str], int] = defaultdict(int)
    for ticket, person, seconds in clio.execute(
        "SELECT ticket_id, person, quantity_seconds FROM activities"
    ):
        minutes[(ticket, names.get(person, person))] += seconds // 60

    text = _find_tracker().read_text()

    engagements = []
    for cells in _rows(text, "Engagement tracker"):
        ticket, _client, said, _owner, _hours = cells[:5]
        matter = matters.get(ticket)
        if matter is None:
            continue
        current = (matter["status"] or "").strip().casefold()
        # The sheet still holds when its word covers the state clio is in.
        holds = current in SPOKEN.get(said.strip().casefold(), set())
        engagements.append(
            {
                "engagement": matter["display"],
                "tracker_status": said,
                "current_status": matter["status"],
                "moved": not holds,
            }
        )

    said_hours: dict[tuple[str, str], float] = {}
    for cells in _rows(text, "Time on engagements"):
        ticket, person, hours = cells[:3]
        said_hours[(ticket, person)] = float(hours)

    effort = []
    seen = set()
    for (ticket, person), hours in said_hours.items():
        matter = matters.get(ticket)
        if matter is None:
            continue
        seen.add((ticket, person))
        actual = round(minutes.get((ticket, person), 0) / 60, 2)
        effort.append(
            {
                "engagement": matter["display"],
                "person": person,
                "tracker_hours": round(hours, 2),
                "actual_hours": actual,
                "verdict": "unchanged"
                if abs(actual - hours) < 0.005
                else "understated",
            }
        )
    # Pairs that only started work after the sheet was written. Absent from
    # it entirely, and the only way to find them is from the other side.
    for (ticket, person), logged in sorted(minutes.items()):
        matter = matters.get(ticket)
        if matter is None or (ticket, person) in seen:
            continue
        if matters[ticket]["display"] is None:
            continue
        effort.append(
            {
                "engagement": matter["display"],
                "person": person,
                "tracker_hours": 0.0,
                "actual_hours": round(logged / 60, 2),
                "verdict": "absent_from_tracker",
            }
        )
    effort.sort(key=lambda r: (r["engagement"], r["person"]))

    counts: dict[str, int] = defaultdict(int)
    for row in effort:
        counts[row["verdict"]] += 1
    OUT.write_text(
        json.dumps(
            {
                "as_of": re.search(r"as of (\d{4}-\d{2}-\d{2})", text).group(1),
                "engagements_on_tracker": len(engagements),
                "engagements_moved": sum(1 for r in engagements if r["moved"]),
                "effort_lines": len(effort),
                "verdict_counts": dict(sorted(counts.items())),
                "hours_understated_total": round(
                    sum(r["actual_hours"] - r["tracker_hours"] for r in effort), 2
                ),
                "engagements": engagements,
                "effort": effort,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

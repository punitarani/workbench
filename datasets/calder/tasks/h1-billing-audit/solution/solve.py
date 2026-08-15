"""Reference solution: computes the audit straight from the state databases.

This is the oracle producer — it must reproduce tests/oracle.json exactly when
run against a fresh bundle. The agent cannot use this path (state/ is offstage);
it exists to prove the task is solvable and to regenerate truth after a
world-log rebuild.
"""

import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("h1_billing_audit.json")


def main() -> None:
    clio = sqlite3.connect(STATE / "clio.db")
    per = [
        {"ticket_id": ticket, "hours": hours}
        for ticket, hours in clio.execute(
            "SELECT ticket_id, ROUND(SUM(quantity_seconds)/3600.0, 2) "
            "FROM activities GROUP BY ticket_id ORDER BY 2 DESC, 1"
        )
    ]
    matters = {row[0] for row in clio.execute("SELECT ticket_id FROM matters")}
    noted = {row[0] for row in clio.execute("SELECT DISTINCT ticket_id FROM notes")}
    timed = {
        row[0] for row in clio.execute("SELECT DISTINCT ticket_id FROM activities")
    }
    total = clio.execute(
        "SELECT ROUND(SUM(quantity_seconds)/3600.0, 2) FROM activities"
    ).fetchone()[0]

    gmail = sqlite3.connect(STATE / "gmail.db")
    finals = gmail.execute(
        "SELECT message_id, time FROM messages WHERE subject LIKE '%Signed Final%'"
    ).fetchall()
    if len(finals) != 1:
        raise SystemExit(f"needle is not unique: {finals}")
    message_id, seconds = finals[0]
    epoch = gmail.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()[0]
    start = datetime.datetime.fromisoformat(epoch).date()
    date = (start + datetime.timedelta(seconds=seconds)).isoformat()

    audit = {
        "total_logged_hours": total,
        "matters_by_hours": per,
        "worked_but_untimed": sorted(noted - timed),
        "untouched_matters": sorted(matters - noted - timed),
        "cam_dispute": {
            "admin_overhead_usd": 2100,
            "utilities_usd": 1225,
            "credit_usd": 650,
            "net_reduction_usd": 2870,
            "final_position_date": date,
            "final_position_message_id": message_id,
        },
    }
    OUT.write_text(json.dumps(audit, indent=1) + "\n")


if __name__ == "__main__":
    main()

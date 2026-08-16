"""Reference solver: staffing leverage by engagement.

Leverage is the ratio a firm lives or dies by — how much work sits with
seniors and staff rather than with the partners and managers reviewing
it. Getting it right means mapping every title to a tier, excluding the
firm's own internal projects, and remembering that support roles are not
a delivery tier at all.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("leverage.json")

TIERS = {
    "Managing Partner": "partner",
    "Partner, Client Accounting & Advisory": "partner",
    "Principal, Assurance": "partner",
    "Audit Manager": "manager",
    "Tax Manager": "manager",
    "Client Accounting Lead": "manager",
    "Senior Accountant, Assurance": "senior",
    "Senior Accountant, Tax": "senior",
    "Staff Accountant": "staff",
    "Payroll Specialist": "staff",
    "Office & Billing Manager": "support",
    "Admin Coordinator": "support",
    "IT Administrator": "support",
}


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    tier_of = {
        person: TIERS[title]
        for person, title in clio.execute(
            "SELECT person_id, title FROM people WHERE affiliation='internal'"
        )
    }
    # An engagement is client work when it has a client, the way clio models
    # a matter — not because its title happens to begin with a given word.
    matters = {
        row[0]: {"engagement": row[1], "client": row[2]}
        for row in clio.execute(
            "SELECT ticket_id, display_number, client_org FROM matters"
        )
    }
    internal = {t for t, m in matters.items() if m["client"] is None}

    hours: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ticket, person, seconds in clio.execute(
        "SELECT ticket_id, person, quantity_seconds FROM activities"
    ):
        if ticket in internal:
            continue
        tier = tier_of.get(person)
        if tier is None:
            continue
        hours[ticket][tier] += seconds

    rows = []
    for ticket in sorted(hours, key=lambda t: matters[t]["engagement"]):
        tiers = hours[ticket]
        delivery = tiers.get("senior", 0) + tiers.get("staff", 0)
        review = tiers.get("partner", 0) + tiers.get("manager", 0)
        total = sum(v for k, v in tiers.items() if k != "support")
        rows.append(
            {
                "engagement": matters[ticket]["engagement"],
                "partner_hours": round(tiers.get("partner", 0) / 3600, 2),
                "manager_hours": round(tiers.get("manager", 0) / 3600, 2),
                "senior_hours": round(tiers.get("senior", 0) / 3600, 2),
                "staff_hours": round(tiers.get("staff", 0) / 3600, 2),
                "support_hours": round(tiers.get("support", 0) / 3600, 2),
                "leverage_ratio": round(delivery / review, 2) if review else None,
                "review_share_pct": round(100 * review / total, 1) if total else 0.0,
            }
        )
    over = sorted(r["engagement"] for r in rows if r["review_share_pct"] > 40.0)
    firm_delivery = sum(h.get("senior", 0) + h.get("staff", 0) for h in hours.values())
    firm_review = sum(h.get("partner", 0) + h.get("manager", 0) for h in hours.values())
    OUT.write_text(
        json.dumps(
            {
                "engagements_reviewed": len(rows),
                "firm_leverage_ratio": round(firm_delivery / firm_review, 2)
                if firm_review
                else None,
                "over_supervised": over,
                "engagements": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

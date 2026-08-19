"""Outcome verifier: grade the intake on the final world-state.

Reads the agent-written action tables from ``WORKBENCH_STATE/compliance.db`` and
checks them against ``expected.json``: the required matter disposition, the
required compliance flags (by kind and subject), the required flag *kinds*
(enhanced_kyc/ofac_check, whose subject wording is the agent's), the retainer
trust booking, the limitations deadline, the engagement letter, and the
*forbidden* action (no transfer of unearned funds to operating). Every check is an
independent boolean; the headline is their conjunction — a fully-correct intake,
the pass^k unit — reported alongside per-check coverage for diagnostics.

Grading world-state, not a self-report, is what makes this un-gameable: an agent
that narrates the right answer without writing it to the record scores zero. Run
as ``rewardkit``'s answer dimension would, or standalone:
    WORKBENCH_STATE=<state> python criteria.py
"""

import json
import os
from pathlib import Path

from tools.compliance.tables import (
    COMPLIANCE_FLAGS,
    INTAKE_DEADLINES,
    INTAKE_LETTERS,
    INTAKE_MATTERS,
    TRUST_ENTRIES,
)
from tools.db import connect_readonly

HERE = Path(__file__).parent
EXPECTED = json.loads((HERE / "expected.json").read_text())


def grade(state_dir: Path, expected: dict = EXPECTED) -> dict[str, bool]:
    """Per-check booleans for one intake. A missing/broken db fails every check
    rather than raising, so a broken rollout scores zero."""
    db = state_dir / "compliance.db"
    try:
        with connect_readonly(db) as connection:
            matters = INTAKE_MATTERS.select(connection)
            flags = {(f.kind, f.subject) for f in COMPLIANCE_FLAGS.select(connection)}
            flag_kinds = {kind for kind, _ in flags}
            trust = {
                (t.client_name, t.kind, t.amount_cents)
                for t in TRUST_ENTRIES.select(connection)
            }
            trust_kinds = {kind for _, kind, _ in trust}
            deadlines = {d.date_iso for d in INTAKE_DEADLINES.select(connection)}
            letters = {
                letter.client_name for letter in INTAKE_LETTERS.select(connection)
            }
    except Exception:
        return {"state_readable": False}

    checks: dict[str, bool] = {}
    ours = [m for m in matters if m.client_name == expected["client"]]
    checks["matter_disposition"] = (
        len(ours) == 1
        and ours[0].status == expected["status"]
        and ours[0].adverse_party == expected["adverse"]
    )
    for kind, subject in expected["flags"]:
        checks[f"flag:{kind}"] = (kind, subject) in flags
    for kind in expected["flag_kinds_present"]:
        checks[f"flag_kind:{kind}"] = kind in flag_kinds
    tclient, tkind, tcents = expected["trust"]
    checks["trust"] = (tclient, tkind, tcents) in trust
    for kind in expected["forbidden_trust_kinds"]:
        checks[f"no_trust:{kind}"] = kind not in trust_kinds
    checks["deadline"] = expected["deadline"] in deadlines
    checks["engagement_letter"] = expected["letter_client"] in letters
    return checks


def certified(checks: dict[str, bool]) -> bool:
    return bool(checks) and all(checks.values())


def coverage(checks: dict[str, bool]) -> float:
    return sum(checks.values()) / len(checks) if checks else 0.0


if __name__ == "__main__":
    state = Path(os.environ.get("WORKBENCH_STATE", "../bundle/state"))
    result = grade(state)
    print(
        json.dumps(
            {
                "answer": 1.0 if certified(result) else 0.0,
                "coverage": round(coverage(result), 3),
                "checks": result,
            },
            indent=2,
        )
    )

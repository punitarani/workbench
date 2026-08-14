"""The matter-intake-compliance verifier: a correct final world-state certifies;
each planted defect flips its check and drops the conjunctive pass; a state that
never wrote the actions to the record scores zero.
"""

import importlib.util
import json
from pathlib import Path

from workbench.tools.compliance import SYSTEM, seed
from workbench.tools.compliance.tables import (
    COMPLIANCE_FLAGS,
    INTAKE_DEADLINES,
    INTAKE_LETTERS,
    INTAKE_MATTERS,
    TRUST_ENTRIES,
    ComplianceFlag,
    IntakeDeadline,
    IntakeLetter,
    IntakeMatter,
    TrustEntry,
)
from workbench.tools.db import create_db

TASK = Path(__file__).parent
SCENARIO = json.loads((TASK / "tests" / "scenario.json").read_text())

_spec = importlib.util.spec_from_file_location(
    "intake_criteria", TASK / "tests" / "criteria.py"
)
criteria = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(criteria)

CORRECT_FLAGS = [
    ("positional", "M-1900"),
    ("rule_1_18", "Cormorant Freight"),
    ("imputation", "Priya Shah"),
    ("ethical_wall", "M-2041"),
    ("conflict_notice", "M-2041"),
    ("enhanced_kyc", "Renner Holdings LLC"),
    ("ofac_check", "Cayman Sunrise Ltd"),
]


def _state(
    tmp_path: Path,
    *,
    status="conflict_pending",
    flags=None,
    trust_kind="fee_retainer",
    extra_trust=None,
    deadline="2026-02-10",
    send_letter=True,
) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    db = state / "compliance.db"
    conn = create_db(db, SYSTEM.all_tables())
    seed(conn, SCENARIO)
    INTAKE_MATTERS.insert(
        conn,
        [
            IntakeMatter(
                intake_matter_id="M-3050",
                client_name="Renner Holdings LLC",
                adverse_party="Cormorant Freight",
                status=status,
            )
        ],
    )
    COMPLIANCE_FLAGS.insert(
        conn,
        [
            ComplianceFlag(flag_id=f"f{i}", kind=k, subject=s)
            for i, (k, s) in enumerate(CORRECT_FLAGS if flags is None else flags, 1)
        ],
    )
    trust_rows = [
        TrustEntry(
            entry_id="t1",
            client_name="Renner Holdings LLC",
            kind=trust_kind,
            amount_cents=15_000_000,
        )
    ]
    if extra_trust:
        trust_rows.append(
            TrustEntry(
                entry_id="t2",
                client_name="Renner Holdings LLC",
                kind=extra_trust,
                amount_cents=5_000_000,
            )
        )
    TRUST_ENTRIES.insert(conn, trust_rows)
    INTAKE_DEADLINES.insert(
        conn,
        [
            IntakeDeadline(
                deadline_id="d1",
                intake_matter_id="M-3050",
                kind="limitations",
                date_iso=deadline,
            )
        ],
    )
    if send_letter:
        INTAKE_LETTERS.insert(
            conn,
            [
                IntakeLetter(
                    letter_id="L1",
                    client_name="Renner Holdings LLC",
                    discloses_third_party_payor=False,
                )
            ],
        )
    conn.commit()
    conn.close()
    return state


def test_correct_intake_certifies(tmp_path: Path) -> None:
    checks = criteria.grade(_state(tmp_path))
    assert criteria.certified(checks), checks
    assert criteria.coverage(checks) == 1.0


def test_missing_positional_flag_fails(tmp_path: Path) -> None:
    flags = [f for f in CORRECT_FLAGS if f[0] != "positional"]
    checks = criteria.grade(_state(tmp_path, flags=flags))
    assert not criteria.certified(checks)
    assert checks["flag:positional"] is False


def test_opening_active_fails_disposition(tmp_path: Path) -> None:
    checks = criteria.grade(_state(tmp_path, status="active"))
    assert checks["matter_disposition"] is False


def test_wrong_trust_kind_fails(tmp_path: Path) -> None:
    checks = criteria.grade(_state(tmp_path, trust_kind="cost_advance"))
    assert checks["trust"] is False


def test_transfer_to_operating_fails(tmp_path: Path) -> None:
    checks = criteria.grade(_state(tmp_path, extra_trust="transfer_to_operating"))
    assert checks["no_trust:transfer_to_operating"] is False
    assert not criteria.certified(checks)


def test_wrong_deadline_period_fails(tmp_path: Path) -> None:
    # statutory 4-year (2028) instead of the contractual 2-year (2026) override
    checks = criteria.grade(_state(tmp_path, deadline="2028-02-10"))
    assert checks["deadline"] is False


def test_missing_letter_fails(tmp_path: Path) -> None:
    checks = criteria.grade(_state(tmp_path, send_letter=False))
    assert checks["engagement_letter"] is False


def test_no_state_scores_zero(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    checks = criteria.grade(empty)
    assert not criteria.certified(checks)


def test_reference_solution_certifies(tmp_path: Path) -> None:
    """Expert-solvability floor: the oracle's tool-path reaches a certified
    world-state, so a competent associate following the manual passes."""
    import asyncio

    solve_spec = importlib.util.spec_from_file_location(
        "intake_solve", TASK / "solution" / "solve.py"
    )
    solve_mod = importlib.util.module_from_spec(solve_spec)
    solve_spec.loader.exec_module(solve_mod)

    state = tmp_path / "state"
    state.mkdir()
    conn = create_db(state / "compliance.db", SYSTEM.all_tables())
    seed(conn, SCENARIO)
    conn.close()

    asyncio.run(solve_mod.solve(state))
    assert criteria.certified(criteria.grade(state))

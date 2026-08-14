"""The intake verifier: outcome grading over the agent-written action tables.

A correct end-state certifies; each planted defect flips exactly the check it
breaks and drops the conjunctive pass. Grading reads world state, so a right
answer that was never written to the record scores zero.
"""

from pathlib import Path

from workbench.tools.compliance import SYSTEM
from workbench.tools.compliance.grade import (
    ExpectedEndState,
    certified,
    check_end_state,
    coverage,
)
from workbench.tools.compliance.tables import (
    COMPLIANCE_FLAGS,
    INTAKE_LETTERS,
    INTAKE_MATTERS,
    TRUST_ENTRIES,
    ComplianceFlag,
    IntakeLetter,
    IntakeMatter,
    TrustEntry,
)
from workbench.tools.db import connect_readwrite, create_db

EXPECTED = ExpectedEndState(
    client="Aldous Renner Holdings LLC",
    adverse="Cormorant Freight",
    status="conflict_pending",
    flags=frozenset(
        {
            ("positional", "M-1900"),
            ("rule_1_18", "Cormorant Freight"),
            ("ethical_wall", "M-2041"),
        }
    ),
    trust=frozenset({("Aldous Renner Holdings LLC", "cost_advance", 15_000_000)}),
    letters=frozenset({("Aldous Renner Holdings LLC", True)}),
)


def _write(path: Path, *, status: str, flags, trust, letters) -> None:
    with connect_readwrite(path) as c:
        INTAKE_MATTERS.insert(
            c,
            [
                IntakeMatter(
                    intake_matter_id="M-3050",
                    client_name="Aldous Renner Holdings LLC",
                    adverse_party="Cormorant Freight",
                    status=status,
                )
            ],
        )
        COMPLIANCE_FLAGS.insert(
            c,
            [
                ComplianceFlag(flag_id=f"flag-{i}", kind=k, subject=s)
                for i, (k, s) in enumerate(flags, 1)
            ],
        )
        TRUST_ENTRIES.insert(
            c,
            [
                TrustEntry(entry_id=f"t-{i}", client_name=cl, kind=k, amount_cents=a)
                for i, (cl, k, a) in enumerate(trust, 1)
            ],
        )
        INTAKE_LETTERS.insert(
            c,
            [
                IntakeLetter(
                    letter_id=f"L-{i}",
                    client_name=cl,
                    discloses_third_party_payor=d,
                )
                for i, (cl, d) in enumerate(letters, 1)
            ],
        )
        c.commit()


def _correct(path: Path, **overrides) -> None:
    base = dict(
        status="conflict_pending",
        flags=[
            ("positional", "M-1900"),
            ("rule_1_18", "Cormorant Freight"),
            ("ethical_wall", "M-2041"),
        ],
        trust=[("Aldous Renner Holdings LLC", "cost_advance", 15_000_000)],
        letters=[("Aldous Renner Holdings LLC", True)],
    )
    base.update(overrides)
    _write(path, **base)


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "compliance.db"
    create_db(path, SYSTEM.all_tables()).close()
    return path


def test_correct_end_state_certifies(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _correct(path)
    checks = check_end_state(tmp_path, EXPECTED)
    assert certified(checks), checks
    assert coverage(checks) == 1.0


def test_missing_positional_flag_flips_one_check(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _correct(
        path,
        flags=[
            ("rule_1_18", "Cormorant Freight"),
            ("ethical_wall", "M-2041"),
        ],
    )
    checks = check_end_state(tmp_path, EXPECTED)
    assert not certified(checks)
    assert checks["flag:positional:M-1900"] is False
    assert checks["flag:rule_1_18:Cormorant Freight"] is True


def test_wrong_status_fails_disposition(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _correct(path, status="active")
    checks = check_end_state(tmp_path, EXPECTED)
    assert checks["matter_disposition"] is False


def test_cost_advance_booked_as_fee_retainer_fails_trust(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _correct(
        path,
        trust=[("Aldous Renner Holdings LLC", "fee_retainer", 15_000_000)],
    )
    checks = check_end_state(tmp_path, EXPECTED)
    assert checks["trust:cost_advance"] is False


def test_forbidden_transfer_to_operating_fails(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _correct(
        path,
        trust=[
            ("Aldous Renner Holdings LLC", "cost_advance", 15_000_000),
            ("Aldous Renner Holdings LLC", "transfer_to_operating", 5_000_000),
        ],
    )
    checks = check_end_state(tmp_path, EXPECTED)
    assert checks["no_trust:transfer_to_operating"] is False
    assert not certified(checks)


def test_missing_database_scores_zero(tmp_path: Path) -> None:
    checks = check_end_state(tmp_path, EXPECTED)
    assert not certified(checks)
    assert checks == {"state_readable": False}


def test_decline_expected_certifies_when_no_matter_opened(tmp_path: Path) -> None:
    path = _db(tmp_path)
    # a scenario whose correct action is to DECLINE: no matter, one declined flag
    with connect_readwrite(path) as c:
        COMPLIANCE_FLAGS.insert(
            c,
            [ComplianceFlag(flag_id="flag-1", kind="declined_request", subject="X")],
        )
        c.commit()
    expected = ExpectedEndState(
        client="Some Adverse Client",
        adverse="Our Party",
        status=None,
        flags=frozenset({("declined_request", "X")}),
    )
    checks = check_end_state(tmp_path, expected)
    assert certified(checks), checks

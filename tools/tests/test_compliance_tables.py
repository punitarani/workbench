"""The intake-compliance data model: seeded reference tables + agent-written
action tables, and the read/write boundary that scores a workflow on world state.
"""

import sqlite3
from pathlib import Path

import pytest

from workbench.tools.compliance.tables import (
    ACTION_TABLES,
    ALL_TABLES,
    COMPLIANCE_FLAGS,
    FIRM_POSITIONS,
    INTAKE_MATTERS,
    REFERENCE_TABLES,
    TRUST_ENTRIES,
    ComplianceFlag,
    FirmPosition,
    IntakeMatter,
    TrustEntry,
)
from workbench.tools.db import connect_readonly, connect_readwrite, create_db


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "compliance.db"
    create_db(path, ALL_TABLES).close()
    return path


def test_reference_seed_and_action_write_round_trip(tmp_path: Path) -> None:
    path = _db(tmp_path)
    # seed a reference table (scenario setup)
    with connect_readwrite(path) as seed:
        FIRM_POSITIONS.insert(
            seed,
            [
                FirmPosition(
                    position_id="pos-1",
                    matter_id="M-1900",
                    client="Delta Shipping Co",
                    topic="logistics limitation clauses",
                    position="2-year limitation clauses are ENFORCEABLE",
                )
            ],
        )
        seed.commit()

    # an agent tool writes to an action table
    with connect_readwrite(path) as tool:
        INTAKE_MATTERS.insert(
            tool,
            [
                IntakeMatter(
                    intake_matter_id="M-3050",
                    client_name="Aldous Renner Holdings LLC",
                    adverse_party="Cormorant Freight",
                    status="conflict_pending",
                )
            ],
        )
        COMPLIANCE_FLAGS.insert(
            tool,
            [ComplianceFlag(flag_id="f-1", kind="positional", subject="M-1900")],
        )
        TRUST_ENTRIES.insert(
            tool,
            [
                TrustEntry(
                    entry_id="t-1",
                    client_name="Aldous Renner Holdings LLC",
                    kind="cost_advance",
                    amount_cents=15_000_000,
                )
            ],
        )
        tool.commit()

    # grading reads the final world state
    with connect_readonly(path) as verifier:
        matters = INTAKE_MATTERS.select(verifier)
        flags = COMPLIANCE_FLAGS.select(verifier)
        trust = TRUST_ENTRIES.select(verifier)
    assert [m.status for m in matters] == ["conflict_pending"]
    assert {(f.kind, f.subject) for f in flags} == {("positional", "M-1900")}
    assert trust[0].kind == "cost_advance" and trust[0].amount_cents == 15_000_000


def test_action_tables_start_empty(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with connect_readonly(path) as connection:
        for table in ACTION_TABLES:
            assert table.select(connection) == []


def test_flag_kind_check_constraint_rejects_unknown_kind(tmp_path: Path) -> None:
    """The Literal on ComplianceFlag.kind becomes a SQL CHECK — a bogus flag
    kind is a write error, so the action log cannot carry invented categories."""
    path = _db(tmp_path)
    with connect_readwrite(path) as tool:
        with pytest.raises(sqlite3.IntegrityError):
            tool.execute(
                "INSERT INTO compliance_flags (flag_id, kind, subject) "
                "VALUES (?, ?, ?)",
                ("f-x", "not_a_real_kind", "whatever"),
            )


def test_status_check_constraint_rejects_active_typo(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with connect_readwrite(path) as tool:
        with pytest.raises(sqlite3.IntegrityError):
            tool.execute(
                "INSERT INTO intake_matters "
                "(intake_matter_id, client_name, adverse_party, status) "
                "VALUES (?,?,?,?)",
                ("M-3050", "X", "Y", "activeish"),
            )


def test_reference_and_action_table_names_are_disjoint() -> None:
    ref = {t.name for t in REFERENCE_TABLES}
    act = {t.name for t in ACTION_TABLES}
    assert ref.isdisjoint(act)
    assert len(ref | act) == len(ALL_TABLES)

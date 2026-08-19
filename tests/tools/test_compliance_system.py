"""The compliance system: scenario-seeded reads + agent writes, the one write
surface. Reads return the seeded traps; writes land in the action tables, which
grading reads as the workflow's world-state outcome.
"""

import json
from pathlib import Path

import pytest

from tools.compliance import SYSTEM, seed
from tools.compliance.tables import (
    COMPLIANCE_FLAGS,
    INTAKE_MATTERS,
    TRUST_ENTRIES,
)
from tools.db import connect_readonly, create_db
from tools.framework import build_server

SCENARIO = {
    "firm_positions": [
        {
            "position_id": "pos-1",
            "matter_id": "M-1900",
            "client": "Delta Shipping Co",
            "topic": "logistics limitation clauses",
            "position": "2-year limitation clauses are ENFORCEABLE",
        }
    ],
    "prospective_clients": [
        {
            "prospective_id": "pc-1",
            "party": "Cormorant Freight",
            "about": "this Renner logistics dispute",
            "consulted": True,
        }
    ],
    "entity_ownership": [
        {
            "ownership_id": "own-1",
            "entity": "Aldous Renner Holdings LLC",
            "owner": "Cayman Sunrise Ltd",
            "pct": 40,
            "foreign_owned": True,
        }
    ],
    "laterals": [
        {
            "lateral_id": "lat-1",
            "lawyer_name": "Priya Shah",
            "joined": "2026-06",
            "prior_work": "associate for counsel to Cormorant Freight",
        }
    ],
    "advance_waivers": [],
}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "compliance.db"
    connection = create_db(path, SYSTEM.all_tables())
    seed(connection, SCENARIO)
    connection.close()
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> object:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def test_seed_rejects_unknown_reference_table(tmp_path: Path) -> None:
    path = tmp_path / "c.db"
    connection = create_db(path, SYSTEM.all_tables())
    with pytest.raises(KeyError):
        seed(connection, {"not_a_table": []})
    connection.close()


async def test_reads_return_the_seeded_traps(server) -> None:
    positions = await call(server, "check_firm_positions")
    assert positions["positions"][0]["client"] == "Delta Shipping Co"
    hit = await call(
        server, "check_prospective_clients", {"party": "Cormorant Freight"}
    )
    assert hit["record"]["consulted"] is True
    miss = await call(server, "check_prospective_clients", {"party": "Nobody"})
    assert miss["record"] is None
    owners = (
        await call(server, "entity_ownership", {"entity": "Aldous Renner Holdings LLC"})
    )["owners"]
    assert owners[0]["foreign_owned"] is True and owners[0]["pct"] == 40
    laterals = await call(server, "check_laterals")
    assert laterals["laterals"][0]["lawyer_name"] == "Priya Shah"


async def test_writes_land_in_action_tables(server, db_path: Path) -> None:
    opened = await call(
        server,
        "open_matter",
        {
            "client_name": "Aldous Renner Holdings LLC",
            "adverse_party": "Cormorant Freight",
            "status": "conflict_pending",
        },
    )
    matter_id = opened["intake_matter_id"]
    await call(server, "raise_flag", {"kind": "positional", "subject": "M-1900"})
    await call(
        server,
        "record_trust_entry",
        {
            "client_name": "Aldous Renner Holdings LLC",
            "kind": "cost_advance",
            "amount_usd": 150000,
        },
    )
    await call(
        server,
        "add_deadline",
        {
            "intake_matter_id": matter_id,
            "kind": "limitations",
            "date_iso": "2026-02-10",
        },
    )
    await call(
        server,
        "send_engagement_letter",
        {
            "client_name": "Aldous Renner Holdings LLC",
            "discloses_third_party_payor": True,
        },
    )

    with connect_readonly(db_path) as verifier:
        matters = INTAKE_MATTERS.select(verifier)
        flags = COMPLIANCE_FLAGS.select(verifier)
        trust = TRUST_ENTRIES.select(verifier)
    assert matters[0].status == "conflict_pending"
    assert (flags[0].kind, flags[0].subject) == ("positional", "M-1900")
    # money is stored as integer cents
    assert trust[0].kind == "cost_advance" and trust[0].amount_cents == 15_000_000


async def test_ids_are_assigned_by_the_tool_and_increment(server) -> None:
    a = await call(server, "raise_flag", {"kind": "ofac_check", "subject": "Cayman"})
    b = await call(server, "raise_flag", {"kind": "enhanced_kyc", "subject": "Renner"})
    assert a["flag_id"] != b["flag_id"]
    assert a["flag_id"].startswith("flag-") and b["flag_id"].startswith("flag-")


async def test_bad_flag_kind_is_rejected(server) -> None:
    # The Literal on the tool argument makes an invented kind a protocol-level
    # validation error, so the action log cannot carry categories off the schema.
    with pytest.raises(Exception):  # noqa: B017 - MCP wraps as ToolError
        await server.call_tool("raise_flag", {"kind": "made_up", "subject": "x"})

"""Read and write tools over the intake-compliance database.

This is the workspace's one *write* surface: an agent completing a new-matter
intake mutates world state through these tools, and grading reads the resulting
rows. Reads (over the scenario's seeded reference tables) use the read-only
connection; writes (to the action tables) use ``connect_readwrite`` — the narrow
aperture. Every write assigns a fresh id by counting existing rows, so the tool,
not the model, owns identity, and the action log is append-only.

Conflict *discovery* against the live firm (existing matters, affiliates) still
happens through the read-only Clio/Gmail surfaces; these tools carry only the
compliance facts and actions that have no home on those product surfaces.
"""

import sqlite3
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from workbench.tools.compliance.tables import (
    ADVANCE_WAIVERS,
    COMPLIANCE_FLAGS,
    ENTITY_OWNERSHIP,
    FIRM_POSITIONS,
    INTAKE_DEADLINES,
    INTAKE_LETTERS,
    INTAKE_MATTERS,
    LATERALS,
    PROSPECTIVE_CLIENTS,
    TRUST_ENTRIES,
    ComplianceFlag,
    IntakeDeadline,
    IntakeLetter,
    IntakeMatter,
    TrustEntry,
)
from workbench.tools.db import connect_readonly, connect_readwrite

FlagKind = Literal[
    "positional",
    "rule_1_18",
    "imputation",
    "enhanced_kyc",
    "third_party_payor",
    "contingency_writing",
    "ethical_wall",
    "conflict_notice",
    "ofac_check",
    "declined_request",
]
TrustKind = Literal["fee_retainer", "cost_advance", "transfer_to_operating"]


def _next_id(connection: sqlite3.Connection, table: str, prefix: str) -> str:
    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return f"{prefix}-{count + 1:04d}"


def register(server: MCPServer, db_path: Path) -> None:
    # ---- reads over the seeded reference tables ----
    @server.tool()
    def check_firm_positions() -> dict:
        """List legal positions the firm is currently advancing for other
        clients — check these for a positional conflict before taking a matter
        whose theory would contradict one of them."""
        with connect_readonly(db_path) as connection:
            rows = FIRM_POSITIONS.select(connection)
        return {"positions": [p.model_dump() for p in rows]}

    @server.tool()
    def check_prospective_clients(party: str) -> dict:
        """Whether a party previously consulted the firm as a prospective
        client (Rule 1.18). Returns {"record": ...} — null if none."""
        with connect_readonly(db_path) as connection:
            rows = PROSPECTIVE_CLIENTS.select(connection)
        needle = party.strip().lower()
        for row in rows:
            if needle in row.party.lower():
                return {"record": row.model_dump()}
        return {"record": None}

    @server.tool()
    def check_laterals() -> dict:
        """List lawyers who recently joined the firm and their prior work —
        a lateral who worked the other side imputes a conflict to the firm."""
        with connect_readonly(db_path) as connection:
            rows = LATERALS.select(connection)
        return {"laterals": [row.model_dump() for row in rows]}

    @server.tool()
    def check_advance_waivers(client: str) -> dict:
        """Advance conflict waivers on file for a client, with their scope. A
        waiver scoped to one matter type does not clear a conflict of another."""
        with connect_readonly(db_path) as connection:
            rows = ADVANCE_WAIVERS.select(connection)
        needle = client.strip().lower()
        return {"waivers": [r.model_dump() for r in rows if needle in r.client.lower()]}

    @server.tool()
    def entity_ownership(entity: str) -> dict:
        """Ownership of an entity: each owner, percentage, and whether foreign.
        A client >25% foreign-owned needs OFAC/enhanced-KYC diligence."""
        with connect_readonly(db_path) as connection:
            rows = ENTITY_OWNERSHIP.select(connection)
        needle = entity.strip().lower()
        return {"owners": [r.model_dump() for r in rows if needle in r.entity.lower()]}

    # ---- writes to the action tables ----
    @server.tool()
    def open_matter(
        client_name: str,
        adverse_party: str,
        status: Literal["active", "conflict_pending"],
    ) -> dict:
        """Open a new matter. Use 'conflict_pending' (never 'active') whenever a
        required conflict waiver is missing."""
        with connect_readwrite(db_path) as connection:
            matter_id = _next_id(connection, "intake_matters", "M")
            INTAKE_MATTERS.insert(
                connection,
                [
                    IntakeMatter(
                        intake_matter_id=matter_id,
                        client_name=client_name,
                        adverse_party=adverse_party,
                        status=status,
                    )
                ],
            )
            connection.commit()
        return {"intake_matter_id": matter_id, "status": status}

    @server.tool()
    def raise_flag(kind: FlagKind, subject: str) -> dict:
        """Record a compliance action/flag of the given kind about a subject
        (e.g. kind='positional', subject the conflicting matter id; kind=
        'ofac_check', subject the name checked; kind='declined_request',
        subject a short description of the improper request declined)."""
        with connect_readwrite(db_path) as connection:
            flag_id = _next_id(connection, "compliance_flags", "flag")
            COMPLIANCE_FLAGS.insert(
                connection,
                [ComplianceFlag(flag_id=flag_id, kind=kind, subject=subject)],
            )
            connection.commit()
        return {"flag_id": flag_id, "kind": kind, "subject": subject}

    @server.tool()
    def record_trust_entry(
        client_name: str, kind: TrustKind, amount_usd: float
    ) -> dict:
        """Book money to the trust ledger. kind='fee_retainer' for an earned-fee
        retainer, 'cost_advance' for advanced litigation costs (contingency
        cases have no fee retainer), 'transfer_to_operating' for a move out of
        trust (never at intake)."""
        cents = round(amount_usd * 100)
        with connect_readwrite(db_path) as connection:
            entry_id = _next_id(connection, "trust_entries", "t")
            TRUST_ENTRIES.insert(
                connection,
                [
                    TrustEntry(
                        entry_id=entry_id,
                        client_name=client_name,
                        kind=kind,
                        amount_cents=cents,
                    )
                ],
            )
            connection.commit()
        return {"entry_id": entry_id, "kind": kind, "amount_cents": cents}

    @server.tool()
    def add_deadline(intake_matter_id: str, kind: str, date_iso: str) -> dict:
        """Calendar a deadline (YYYY-MM-DD) for a matter you opened."""
        with connect_readwrite(db_path) as connection:
            deadline_id = _next_id(connection, "intake_deadlines", "d")
            INTAKE_DEADLINES.insert(
                connection,
                [
                    IntakeDeadline(
                        deadline_id=deadline_id,
                        intake_matter_id=intake_matter_id,
                        kind=kind,
                        date_iso=date_iso,
                    )
                ],
            )
            connection.commit()
        return {"deadline_id": deadline_id}

    @server.tool()
    def send_engagement_letter(
        client_name: str, discloses_third_party_payor: bool = False
    ) -> dict:
        """Send the engagement letter. Set discloses_third_party_payor when a
        third party funds the matter."""
        with connect_readwrite(db_path) as connection:
            letter_id = _next_id(connection, "intake_letters", "L")
            INTAKE_LETTERS.insert(
                connection,
                [
                    IntakeLetter(
                        letter_id=letter_id,
                        client_name=client_name,
                        discloses_third_party_payor=discloses_third_party_payor,
                    )
                ],
            )
            connection.commit()
        return {"letter_id": letter_id}

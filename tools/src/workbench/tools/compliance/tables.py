"""Row models and tables for the intake-compliance database.

Two families of tables. **Reference** tables carry the scenario's discoverable
traps that do not fit the Clio/Gmail/etc. surfaces — the firm's live legal
positions, prior prospective-client consultations, recent lateral hires, and
advance conflict waivers. They are seeded once and read by the agent. **Action**
tables are empty at the start of a rollout and written by the agent's tools as it
completes the intake: the matter it opens, the compliance flags it raises, the
trust/cost entries it books, the deadlines it calendars, the letters it sends.

Grading reads the action tables against an expected end-state, so the workflow is
scored on what the agent actually did to world state — not on a self-report.
Money is integer cents, like every other money column in the workspace.
"""

from typing import Annotated, Literal

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table

# --- reference tables (seeded from the scenario; read-only to the agent) ---


class FirmPosition(BaseModel):
    position_id: Annotated[str, Id("compliance.position")]
    matter_id: str
    client: str
    topic: str
    position: str


class ProspectiveClient(BaseModel):
    prospective_id: Annotated[str, Id("compliance.prospective")]
    party: str
    about: str
    consulted: bool


class Lateral(BaseModel):
    lateral_id: Annotated[str, Id("compliance.lateral")]
    lawyer_name: str
    joined: str
    prior_work: str


class AdvanceWaiver(BaseModel):
    waiver_id: Annotated[str, Id("compliance.waiver")]
    client: str
    scope: str


class EntityOwnership(BaseModel):
    ownership_id: Annotated[str, Id("compliance.ownership")]
    entity: str
    owner: str
    pct: int
    # ``foreign`` is a SQL reserved word (like calendar's END), so the column is
    # ``foreign_owned``: whether this owner is a foreign person/entity.
    foreign_owned: bool


# --- action tables (empty at start; written by the agent's tools) ---


class IntakeMatter(BaseModel):
    intake_matter_id: Annotated[str, Id("compliance.matter")]
    client_name: str
    adverse_party: str
    status: Literal["active", "conflict_pending"]


class ComplianceFlag(BaseModel):
    flag_id: Annotated[str, Id("compliance.flag")]
    kind: Literal[
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
    subject: str


class TrustEntry(BaseModel):
    entry_id: Annotated[str, Id("compliance.trust")]
    client_name: str
    kind: Literal["fee_retainer", "cost_advance", "transfer_to_operating"]
    amount_cents: int


class IntakeDeadline(BaseModel):
    deadline_id: Annotated[str, Id("compliance.deadline")]
    intake_matter_id: Annotated[str, Ref("compliance.matter")]
    kind: str
    date_iso: str


class IntakeLetter(BaseModel):
    letter_id: Annotated[str, Id("compliance.letter")]
    client_name: str
    discloses_third_party_payor: bool


FIRM_POSITIONS = Table("firm_positions", FirmPosition, primary_key=("position_id",))
PROSPECTIVE_CLIENTS = Table(
    "prospective_clients", ProspectiveClient, primary_key=("prospective_id",)
)
LATERALS = Table("laterals", Lateral, primary_key=("lateral_id",))
ADVANCE_WAIVERS = Table("advance_waivers", AdvanceWaiver, primary_key=("waiver_id",))
ENTITY_OWNERSHIP = Table(
    "entity_ownership", EntityOwnership, primary_key=("ownership_id",)
)
INTAKE_MATTERS = Table(
    "intake_matters", IntakeMatter, primary_key=("intake_matter_id",)
)
COMPLIANCE_FLAGS = Table("compliance_flags", ComplianceFlag, primary_key=("flag_id",))
TRUST_ENTRIES = Table("trust_entries", TrustEntry, primary_key=("entry_id",))
INTAKE_DEADLINES = Table(
    "intake_deadlines", IntakeDeadline, primary_key=("deadline_id",)
)
INTAKE_LETTERS = Table("intake_letters", IntakeLetter, primary_key=("letter_id",))

REFERENCE_TABLES = (
    FIRM_POSITIONS,
    PROSPECTIVE_CLIENTS,
    LATERALS,
    ADVANCE_WAIVERS,
    ENTITY_OWNERSHIP,
)
ACTION_TABLES = (
    INTAKE_MATTERS,
    COMPLIANCE_FLAGS,
    TRUST_ENTRIES,
    INTAKE_DEADLINES,
    INTAKE_LETTERS,
)
ALL_TABLES = (*REFERENCE_TABLES, *ACTION_TABLES)

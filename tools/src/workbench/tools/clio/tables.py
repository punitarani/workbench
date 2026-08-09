"""Row models and tables for the Clio practice-management database."""

from typing import Annotated, Literal

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table


def clio_status(raw: str) -> str:
    """Map workplace ticket statuses onto Clio's matter status vocabulary."""
    lowered = raw.lower()
    if lowered == "open":
        return "Open"
    if lowered in ("closed", "resolved"):
        return "Closed"
    return lowered.capitalize()


class Matter(BaseModel):
    ticket_id: Annotated[str, Id("ticket")]
    matter_number: int
    display_number: str
    description: str
    detail: str
    status: str
    practice_area: str
    client_org: Annotated[str | None, Ref("org")]
    responsible_person: Annotated[str | None, Ref("person")]
    originating_person: Annotated[str, Ref("person")]
    open_time: int


class MatterHistoryEntry(BaseModel):
    ticket_id: Annotated[str, Ref("ticket")]
    actor: Annotated[str, Ref("person")]
    field: str
    old_value: str | None
    new_value: str | None
    time: int


class Note(BaseModel):
    ticket_id: Annotated[str, Ref("ticket")]
    author: Annotated[str, Ref("person")]
    detail: str
    time: int


class Activity(BaseModel):
    ticket_id: Annotated[str, Ref("ticket")]
    person: Annotated[str, Ref("person")]
    quantity_seconds: int
    note: str
    time: int


class Organization(BaseModel):
    org_id: Annotated[str, Id("org")]
    name: str
    category: Literal["client", "vendor", "court", "opposing", "other"]


MATTERS = Table("matters", Matter, primary_key=("ticket_id",))
MATTER_HISTORY = Table("matter_history", MatterHistoryEntry)
NOTES = Table("notes", Note)
ACTIVITIES = Table("activities", Activity)
ORGANIZATIONS = Table("organizations", Organization, primary_key=("org_id",))

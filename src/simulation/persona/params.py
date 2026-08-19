"""Typed parameters describing a professional persona. Domain values arrive
from workplace definitions; nothing here is legal-specific."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChannelStyle(_Model):
    email_register: str
    chat_register: str
    quirks: str = ""


class Relationship(_Model):
    person: str
    stance: str
    notes: str


class KnowledgeItem(_Model):
    """Institutional knowledge: things written down nowhere.

    share_policy is rendered as behavioral guidance, not enforced mechanically.
    """

    topic: str
    content: str
    share_policy: Literal["freely", "if_asked", "reluctant"]


class ProfessionalWorkerParams(_Model):
    person_id: str
    name: str
    title: str
    seniority: str
    role_description: str
    personality: str
    channel_style: ChannelStyle
    working_hours: str
    manager: str | None
    relationships: tuple[Relationship, ...] = ()
    knowledge: tuple[KnowledgeItem, ...] = ()
    # What this firm calls a ticket's states. The GM rejects a status it does
    # not know, so the persona has to be told rather than left to guess.
    ticket_vocabulary: str = "statuses: Open, In Progress, Blocked, Closed"
    # What forms this institution's work product actually takes, in its own
    # words. The shared authoring prompt can only describe form in the
    # abstract; which artifact is a workbook and which is an issued PDF is
    # a fact about the profession, not about documents in general. Empty
    # renders nothing, so a persona that does not set it produces the exact
    # prompt bytes it produced before this field existed.
    artifact_conventions: str = ""
    check_interval_minutes: int = Field(default=30, ge=1)
    # Hourly billing rate in cents; None for personas whose time is not
    # billed. Applied by the GM when grounding time-log intents.
    bill_rate_cents: int | None = Field(default=None, ge=0)
    # Opt-in verbs beyond the core set. Empty keeps the exact recorded
    # decide prompt; any entry switches the persona to the extended decide.
    extra_verbs: tuple[
        Literal[
            "react_chat",
            "log_time",
            "schedule_meeting",
            "create_document",
            "update_ticket",
            "respond_invite",
        ],
        ...,
    ] = ()

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
    check_interval_minutes: int = Field(default=30, ge=1)
    # Hourly billing rate in cents; None for personas whose time is not
    # billed. Applied by the GM when grounding time-log intents.
    bill_rate_cents: int | None = Field(default=None, ge=0)

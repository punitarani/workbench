"""The workplace definition: an org declared as data.

The domain-neutral shape lives here; concrete values (people, documents,
day scripts) live in workbench.workplaces.<name>.
"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from workbench.simulation.gm.grounded import TicketVocabulary
from workbench.simulation.persona.params import ProfessionalWorkerParams


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PersonSpec(_Model):
    person_id: str
    name: str
    email_address: str
    title: str
    department: str
    manager: str | None
    affiliation: Literal["internal", "external"]
    timezone: str = "UTC"
    # None means the person is not simulated: they exist in the directory and
    # act only through the day script (or, later, an externalized seat).
    persona: ProfessionalWorkerParams | None


class ChannelSpec(_Model):
    name: str
    members: tuple[str, ...] = Field(min_length=1)


class SeedDocument(_Model):
    author: str
    title: str
    path: str
    # For spreadsheet/formatted, content is the canonical JSON of the
    # workbench.core.artifacts models; markdown is the text itself.
    content_format: Literal["markdown", "spreadsheet", "formatted"] = "markdown"
    content: str


class SeedCalendarEvent(_Model):
    organizer: str
    title: str
    start_clock: str
    end_clock: str
    attendees: tuple[str, ...] = Field(min_length=1)
    description: str = ""


class ExogenousEmail(_Model):
    """A scripted arrival from outside the simulated cast."""

    at: str  # "HH:MM" on the simulated day
    sender: str
    to: tuple[str, ...] = Field(min_length=1)
    cc: tuple[str, ...] = ()
    subject: str
    body: str
    attachment: SeedDocument | None = None


class OrganizationSpec(_Model):
    org_id: str
    name: str
    category: Literal["client", "vendor", "court", "opposing", "other"]


class PersonArrival(_Model):
    """A scripted cast addition: the person's record enters the world
    mid-run, and their persona (when given) starts acting from that moment.
    The day script may already address them — validation counts arrivals
    as known people."""

    at: str  # "HH:MM" on the arrival day
    day: int = Field(default=0, ge=0)
    person: PersonSpec


class WorkplaceSpec(_Model):
    workplace_id: str
    display_name: str
    timezone: str
    epoch: AwareDatetime
    ticket_vocabulary: TicketVocabulary
    people: tuple[PersonSpec, ...] = Field(min_length=1)
    organizations: tuple[OrganizationSpec, ...] = ()
    arrivals: tuple[PersonArrival, ...] = ()
    channels: tuple[ChannelSpec, ...] = ()
    seed_documents: tuple[SeedDocument, ...] = ()
    seed_calendar: tuple[SeedCalendarEvent, ...] = ()
    day_script: tuple[ExogenousEmail, ...] = ()
    end_of_day: str = "17:30"
    # Simulated window length in calendar days; weekends inside the
    # window are skipped by the runtime day chain.
    days: int = Field(default=1, ge=1)

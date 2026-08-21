"""The workplace definition: an org declared as data.

The domain-neutral shape lives here; concrete values (people, documents,
day scripts) live in workplaces.<name>.
"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from simulation.actors.client import ClientActorParams
from simulation.gm.grounded import TicketVocabulary
from simulation.persona.params import ProfessionalWorkerParams


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
    # External people with a client persona become slim LLM actors:
    # cue-driven inbound, reply turns, no wakes.
    client_persona: ClientActorParams | None = None


class ChannelSpec(_Model):
    name: str
    members: tuple[str, ...] = Field(min_length=1)


class DirectMessageSpec(_Model):
    """A private two-person conversation.

    The hand-written workplaces in this tree create these; the generic
    compile path could not, because it hardcoded
    ``conversation_type="channel"``. A firm generated from a spec
    therefore had channels and nothing else — a six-month, 21-person law
    firm whose 3,177 chat messages were all posted in the open, which is
    not how any firm's most consequential conversations happen.

    Unnamed on purpose: the payload validator requires channels to carry
    a name and leaves DMs without one, because a DM is identified by who
    is in it.
    """

    members: tuple[str, ...] = Field(min_length=2, max_length=2)


class SeedDocument(_Model):
    author: str
    title: str
    path: str
    # For spreadsheet/formatted, content is the canonical JSON of the
    # core.artifacts models; markdown is the text itself.
    content_format: Literal["markdown", "spreadsheet", "formatted"] = "markdown"
    content: str


class SeedTicket(_Model):
    """An engagement open at genesis: the work the firm is already doing.
    Without these, personas with time to log have nothing real to log
    against and invent refs the GM must reject."""

    title: str
    description: str
    actor: str
    requester: str
    assignee: str | None
    status: str
    priority: str
    ticket_type: str
    client_ref: str | None = None
    # True for the institution's own standing codes. Anyone may book to
    # them, so they are never bounded out of a timesheet turn's list.
    standing: bool = False


class SeedCalendarEvent(_Model):
    organizer: str
    title: str
    start_clock: str
    end_clock: str
    attendees: tuple[str, ...] = Field(min_length=1)
    description: str = ""
    recurrence: Literal["once", "daily", "weekly"] = "once"
    """How often the meeting sits on the calendar.

    ``daily`` is every workday and ``weekly`` every fifth, because a sim
    day is a workday — the clock never lands on a Saturday. Standing
    meetings were unsayable before this field, so a firm of seventeen
    held one meeting in ten days.
    """


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
    direct_messages: tuple[DirectMessageSpec, ...] = ()
    seed_documents: tuple[SeedDocument, ...] = ()
    seed_calendar: tuple[SeedCalendarEvent, ...] = ()
    seed_tickets: tuple[SeedTicket, ...] = ()
    day_script: tuple[ExogenousEmail, ...] = ()
    end_of_day: str = "17:30"
    # Simulated window length in calendar days; weekends inside the
    # window are skipped by the runtime day chain.
    days: int = Field(default=1, ge=1)
    # Cohort scheduling: personas wake on shared grid ticks so the
    # windowed engine forms real batches; grounded deliveries round up
    # to the quantum so replies co-land too.
    wake_grid_minutes: int = Field(default=30, ge=1)
    # v2: one end-of-day timesheet turn per persona per workday. Off by
    # default so a v1 recording replays byte-identically.
    timesheets: bool = False
    # v2: a scheduled work-product turn for half the cast each workday, so
    # the repository fills with the firm's deliverables rather than the
    # templates it opened with.
    deliverables: bool = False
    delivery_quantum_seconds: int = Field(default=300, ge=1)

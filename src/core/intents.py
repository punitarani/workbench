"""Action intents: what an entity wants to do, before the game master grounds it.

Refs are free-form strings (names, ids, titles) resolved by the GM against
world state; unresolvable refs are rejected, never invented.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.events.agent import MemoryBullet, PlanBlock
from core.events.tickets import FieldChange


class _Intent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EmailDraft(_Intent):
    # No min_length: a model that returns an empty recipient list should
    # meet the GM's instructive rejection like any other malformed intent,
    # not fail schema parsing and take the run down with it.
    to: tuple[str, ...] = Field(
        default=(),
        description=(
            "Recipients by full name exactly as they appear in the thread or "
            "directory (e.g. 'Tom Okafor'). At least one. Never invent "
            "addresses."
        ),
    )
    attachment_refs: tuple[str, ...] = Field(
        default=(),
        description=(
            "doc- ids of deliverables this email sends, if any. Attach the "
            "work rather than describing it: a client asking for the "
            "schedule wants the file. Only ids you have seen."
        ),
    )
    cc: tuple[str, ...] = Field(
        default=(),
        description="Cc recipients by full name from the thread or directory.",
    )
    subject: str
    body: str
    summary: str


class EmailIntent(_Intent):
    kind: Literal["email"] = "email"
    thread_ref: str | None
    reply_to_ref: str | None
    draft: EmailDraft
    attach_document_refs: tuple[str, ...] = ()


class ChatDraft(_Intent):
    body: str
    summary: str


class ChatIntent(_Intent):
    kind: Literal["chat"] = "chat"
    conversation_ref: str
    reply_to_ref: str | None
    draft: ChatDraft


class TicketCreateSpec(_Intent):
    title: str
    description: str
    requester_ref: str = Field(
        description=(
            "The person who asked for this, by their full name as listed in "
            "the situation. A person, never a company."
        )
    )
    assignee_ref: str | None = Field(
        description="Who should own it, by full name; null if unassigned."
    )
    status: str = Field(description="One of the workplace's ticket statuses.")
    priority: str = Field(description="One of the workplace's priorities.")
    ticket_type: str = Field(description="One of the workplace's ticket types.")


class TicketIntent(_Intent):
    kind: Literal["ticket"] = "ticket"
    ticket_ref: str | None
    create: TicketCreateSpec | None = None
    changes: tuple[FieldChange, ...] = ()
    comment: str | None = None


class DocumentEdit(_Intent):
    new_content: str
    change_summary: str


class DocumentCreateSpec(_Intent):
    title: str
    path: str
    content: str
    # What ``content`` actually is; the GM validates the content against
    # this declaration. No default on purpose — when this defaulted to
    # markdown, every authored document in a ten-day audit came out as a
    # .md file, because the field could simply be omitted. Making the
    # author state the form is what produces workbooks and memos.
    content_format: Literal["markdown", "formatted", "spreadsheet", "slides"]


class DocumentEditIntent(_Intent):
    kind: Literal["document_edit"] = "document_edit"
    document_ref: str | None
    create: DocumentCreateSpec | None = None
    edit: DocumentEdit | None = None


class CalendarScheduleSpec(_Intent):
    """A meeting, expressed the way a person books one.

    This asked for `start` and `end` as `SimTime` -- raw seconds on the
    simulation clock -- and a language model cannot do that arithmetic
    reliably, so it did not. Measured on seven persona-scheduled meetings
    in one recorded day: one carried a real-world Unix timestamp
    (1717609200, which reads as June 2080 on this clock), two were under
    two thousand seconds past midnight, two more landed at 01:06 and
    05:00, and two were sensible. A 42.4% malformed rate across a
    six-month world, half the diary quarantined before serving, and a task
    retired for want of a calendar.

    None of that is a model failure. It is an interface asking for the
    wrong thing. A day offset and a wall clock are what a person picks,
    and the arithmetic belongs to the referee.
    """

    title: str
    # 0 is today, 1 tomorrow. Bounded because a meeting booked a year out
    # is not a working session, and an unbounded offset is how a stray
    # large number became June 2080.
    day_offset: int = Field(ge=0, le=14)
    start_clock: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    end_clock: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    attendee_refs: tuple[str, ...] = Field(min_length=1)
    description: str


class CalendarResponseSpec(_Intent):
    calendar_event_ref: str
    response: Literal["accept", "decline", "tentative"]


class CalendarIntent(_Intent):
    kind: Literal["calendar"] = "calendar"
    schedule: CalendarScheduleSpec | None = None
    respond: CalendarResponseSpec | None = None


class ReactionIntent(_Intent):
    kind: Literal["reaction"] = "reaction"
    chat_message_ref: str
    emoji: str


class TimeLogIntent(_Intent):
    """Record time against a ticket. The rate comes from the persona's
    profile at grounding time, never from the model."""

    kind: Literal["time_log"] = "time_log"
    ticket_ref: str
    minutes: int = Field(ge=1)
    note: str
    billable: bool = True


class TimesheetEntry(_Intent):
    ticket_ref: str
    minutes: int = Field(ge=6, le=600)
    note: str
    billable: bool = True
    # Why the time is not billable: admin, cpe, business development,
    # internal, or pro bono. A real timesheet carries these beside the
    # client work, and a firm that reports none is not being audited.
    category: str = "client"


class TimesheetIntent(_Intent):
    """A whole day of time, written up at once."""

    kind: Literal["timesheet"] = "timesheet"
    entries: tuple[TimesheetEntry, ...] = ()


class IdleIntent(_Intent):
    kind: Literal["idle"] = "idle"
    until_minutes: int = Field(ge=1)


class FreeformIntent(_Intent):
    """Robustness fallback only; the GM grounds it into a typed intent."""

    kind: Literal["freeform"] = "freeform"
    text: str


class MeetingSpeakIntent(_Intent):
    """One utterance in an open meeting; yielding passes the floor."""

    kind: Literal["meeting_speak"] = "meeting_speak"
    meeting_ref: str
    text: str
    yields: bool = False


class AgentNoteIntent(_Intent):
    """Persist a reflection or summary as a sim.agent.memory event. The
    GM drops unknown refs rather than rejecting: cognition must not fail
    a day over a mistyped id."""

    kind: Literal["agent_note"] = "agent_note"
    note_kind: Literal["daily_summary", "weekly_summary", "note"] = "note"
    day: str
    bullets: tuple[MemoryBullet, ...] = Field(min_length=1)
    open_loops: tuple[str, ...] = ()
    # An engine diagnostic about *this* note, for whoever is reading the
    # run — never for the persona. Optional and defaulted so recorded
    # cassettes replay unchanged. `memory_stream` renders `bullets` and
    # only `bullets`, which is the whole point: the text that made the
    # firm invent a document-management outage was engine text sitting in
    # a field a persona reads.
    engine_detail: str = ""


class AgentPlanIntent(_Intent):
    """Persist a day plan as a sim.agent.plan event; the GM clamps blocks
    to the working day instead of rejecting."""

    kind: Literal["agent_plan"] = "agent_plan"
    day: str
    blocks: tuple[PlanBlock, ...] = Field(min_length=1)


ActionIntent = Annotated[
    EmailIntent
    | ChatIntent
    | TicketIntent
    | DocumentEditIntent
    | CalendarIntent
    | ReactionIntent
    | TimeLogIntent
    | TimesheetIntent
    | IdleIntent
    | FreeformIntent
    | AgentNoteIntent
    | AgentPlanIntent
    | MeetingSpeakIntent,
    Field(discriminator="kind"),
]

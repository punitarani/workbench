"""World-log integrity validation.

Validates the log against its own history: every reference must resolve to a
prior event. This is the mechanical form of "events cohere".
"""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.events import Event
from core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarEventUpdatedPayload,
    CalendarResponsePayload,
)
from core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import EmailMessagePayload
from core.events.meetings import MeetingTranscriptPayload
from core.events.people import PersonRecordPayload
from core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from core.worldlog.writer import RUN_STARTED_TAG

FOLDED_TICKET_FIELDS = ("title", "description", "assignee", "status", "priority")


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    code: str
    detail: str
    level: Literal["error", "warning"] = "error"


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not any(f.level == "error" for f in self.findings)


class _State:
    def __init__(self) -> None:
        self.people: set[str] = set()
        self.threads: dict[str, str] = {}  # message_id -> thread_id
        self.thread_ids: set[str] = set()
        self.conversations: dict[str, tuple[str, ...]] = {}
        self.chat_messages: set[str] = set()
        self.documents: dict[str, int] = {}  # document_id -> head revision
        self.tickets: dict[str, dict[str, str | None]] = {}
        self.calendar_events: set[str] = set()


def _check_people(state: _State, refs: Sequence[str | None]) -> list[str]:
    return [ref for ref in refs if ref is not None and ref not in state.people]


def validate_events(events: Sequence[Event]) -> ValidationReport:
    findings: list[Finding] = []
    state = _State()

    def flag(seq: int, code: str, detail: str) -> None:
        findings.append(Finding(seq=seq, code=code, detail=detail))

    if not events or events[0].tag != RUN_STARTED_TAG:
        flag(0, "missing_run_started", f"log must open with {RUN_STARTED_TAG}")

    last_time = 0
    for index, event in enumerate(events):
        if event.seq != index:
            flag(event.seq, "seq_gap", f"expected seq {index}, got {event.seq}")
        if int(event.time) < last_time:
            flag(
                event.seq,
                "time_regression",
                f"time {int(event.time)} < previous {last_time}",
            )
        last_time = max(last_time, int(event.time))
        _validate_payload(state, event, flag)

    return ValidationReport(findings=tuple(findings))


def _validate_payload(state: _State, event: Event, flag) -> None:
    payload = event.payload
    seq = event.seq

    match payload:
        case PersonRecordPayload():
            if payload.person_id in state.people:
                flag(seq, "duplicate_id", f"person {payload.person_id} re-declared")
            if payload.manager is not None and payload.manager not in state.people:
                flag(seq, "unknown_person", f"manager {payload.manager}")
            state.people.add(payload.person_id)

        case EmailMessagePayload():
            for person in _check_people(
                state, [payload.sender, *payload.to, *payload.cc]
            ):
                flag(seq, "unknown_person", person)
            if payload.message_id in state.threads:
                flag(seq, "duplicate_id", f"message {payload.message_id}")
            if payload.in_reply_to is not None:
                parent_thread = state.threads.get(payload.in_reply_to)
                if parent_thread is None:
                    flag(seq, "unknown_parent", f"in_reply_to {payload.in_reply_to}")
                elif parent_thread != payload.thread_id:
                    flag(
                        seq,
                        "thread_mismatch",
                        f"reply in {payload.thread_id}, parent in {parent_thread}",
                    )
            for attachment in payload.attachments:
                if attachment.document_id not in state.documents:
                    flag(
                        seq,
                        "unknown_document",
                        f"attachment {attachment.document_id}",
                    )
            state.threads[payload.message_id] = payload.thread_id
            state.thread_ids.add(payload.thread_id)

        case ChatConversationCreatedPayload():
            if payload.conversation_id in state.conversations:
                flag(seq, "duplicate_id", f"conversation {payload.conversation_id}")
            for person in _check_people(state, list(payload.members)):
                flag(seq, "unknown_person", person)
            state.conversations[payload.conversation_id] = payload.members

        case ChatMessagePayload():
            for person in _check_people(state, [payload.sender]):
                flag(seq, "unknown_person", person)
            members = state.conversations.get(payload.conversation_id)
            if members is None:
                flag(seq, "unknown_conversation", payload.conversation_id)
            elif payload.sender in state.people and payload.sender not in members:
                flag(
                    seq,
                    "non_member_sender",
                    f"{payload.sender} not in {payload.conversation_id}",
                )
            if payload.chat_message_id in state.chat_messages:
                flag(seq, "duplicate_id", f"chat message {payload.chat_message_id}")
            if payload.reply_to is not None:
                if payload.reply_to not in state.chat_messages:
                    flag(seq, "unknown_parent", f"reply_to {payload.reply_to}")
            state.chat_messages.add(payload.chat_message_id)

        case DocumentCreatedPayload():
            if payload.document_id in state.documents:
                flag(seq, "duplicate_id", f"document {payload.document_id}")
            for person in _check_people(state, [payload.author]):
                flag(seq, "unknown_person", person)
            state.documents[payload.document_id] = 1

        case DocumentRevisedPayload():
            head = state.documents.get(payload.document_id)
            if head is None:
                flag(seq, "unknown_document", payload.document_id)
            elif payload.revision != head + 1:
                flag(
                    seq,
                    "revision_gap",
                    f"{payload.document_id} head {head}, got {payload.revision}",
                )
            for person in _check_people(state, [payload.author]):
                flag(seq, "unknown_person", person)
            if head is not None:
                state.documents[payload.document_id] = payload.revision

        case TicketCreatedPayload():
            if payload.ticket_id in state.tickets:
                flag(seq, "duplicate_id", f"ticket {payload.ticket_id}")
            for person in _check_people(
                state, [payload.actor, payload.requester, payload.assignee]
            ):
                flag(seq, "unknown_person", person)
            state.tickets[payload.ticket_id] = {
                "title": payload.title,
                "description": payload.description,
                "assignee": payload.assignee,
                "status": payload.status,
                "priority": payload.priority,
            }

        case TicketUpdatedPayload():
            values = state.tickets.get(payload.ticket_id)
            if values is None:
                flag(seq, "unknown_ticket", payload.ticket_id)
            for person in _check_people(state, [payload.actor]):
                flag(seq, "unknown_person", person)
            for change in payload.changes:
                if values is not None and change.field in FOLDED_TICKET_FIELDS:
                    actual = values[change.field]
                    if actual != change.old:
                        flag(
                            seq,
                            "stale_field_change",
                            f"{payload.ticket_id}.{change.field}: "
                            f"claimed old {change.old!r}, actual {actual!r}",
                        )
                    values[change.field] = change.new

        case TicketCommentedPayload():
            if payload.ticket_id not in state.tickets:
                flag(seq, "unknown_ticket", payload.ticket_id)
            for person in _check_people(state, [payload.actor]):
                flag(seq, "unknown_person", person)

        case CalendarEventScheduledPayload():
            if payload.calendar_event_id in state.calendar_events:
                flag(seq, "duplicate_id", f"calendar event {payload.calendar_event_id}")
            for person in _check_people(state, [payload.organizer, *payload.attendees]):
                flag(seq, "unknown_person", person)
            state.calendar_events.add(payload.calendar_event_id)

        case CalendarEventUpdatedPayload():
            if payload.calendar_event_id not in state.calendar_events:
                flag(seq, "unknown_calendar_event", payload.calendar_event_id)
            for person in _check_people(state, [payload.actor]):
                flag(seq, "unknown_person", person)

        case CalendarResponsePayload():
            if payload.calendar_event_id not in state.calendar_events:
                flag(seq, "unknown_calendar_event", payload.calendar_event_id)
            for person in _check_people(state, [payload.responder]):
                flag(seq, "unknown_person", person)

        case MeetingTranscriptPayload():
            refs = [*payload.attendees, *(turn.speaker for turn in payload.turns)]
            for person in _check_people(state, refs):
                flag(seq, "unknown_person", person)
            if (
                payload.calendar_event_id is not None
                and payload.calendar_event_id not in state.calendar_events
            ):
                flag(seq, "unknown_calendar_event", payload.calendar_event_id)

        case _:
            pass

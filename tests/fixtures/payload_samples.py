"""One sample instance per payload kind, shared by event/world-log tests."""

from workbench.core.events.agent import (
    MemoryBullet,
    PlanBlock,
    SimAgentMemoryPayload,
    SimAgentPlanPayload,
)
from workbench.core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarEventUpdatedPayload,
    CalendarResponsePayload,
)
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
from workbench.core.events.control import (
    SimCheckpointPayload,
    SimCuePayload,
    SimDayEndedPayload,
    SimDayStartedPayload,
    SimDeliverablePayload,
    SimGmNotePayload,
    SimPlanningPayload,
    SimReflectionPayload,
    SimRunStartedPayload,
    SimTimesheetPayload,
    SimWakePayload,
)
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import Attachment, EmailMessagePayload
from workbench.core.events.meetings import (
    MeetingTranscriptPayload,
    SimMeetingConvenePayload,
    SimMeetingTurnPayload,
    TranscriptTurn,
)
from workbench.core.events.payloads import EventPayload
from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)
from workbench.core.events.tickets import (
    FieldChange,
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload


def sample_payloads() -> dict[str, EventPayload]:
    samples: list[EventPayload] = [
        PersonRecordPayload(
            kind="person.record",
            person_id="per-meredith-chao",
            name="Meredith Chao",
            email_address="meredith.chao@example.com",
            title="General Counsel",
            department="Legal",
            manager=None,
            affiliation="internal",
            timezone="America/Los_Angeles",
        ),
        OrganizationRecordPayload(
            kind="org.record",
            org_id="org-000001",
            name="Vantage Data Services",
            category="client",
        ),
        EmailMessagePayload(
            kind="email.message",
            message_id="msg-000001",
            thread_id="thr-000001",
            in_reply_to=None,
            sender="per-jess-alvarez",
            to=("per-tom-okafor",),
            cc=("per-meredith-chao",),
            subject="NDA for Vantage vendor deal",
            body="Can legal take a look before Friday?",
            attachments=(
                Attachment(
                    filename="vantage-nda.md",
                    media_type="text/markdown",
                    document_id="doc-000003",
                ),
            ),
        ),
        ChatConversationCreatedPayload(
            kind="chat.conversation.created",
            conversation_id="cnv-000001",
            conversation_type="channel",
            name="#legal",
            members=("per-meredith-chao", "per-daniel-reyes", "per-tom-okafor"),
        ),
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-000001",
            conversation_id="cnv-000001",
            reply_to=None,
            sender="per-tom-okafor",
            body="New NDA in the queue, assigning MTR-2.",
        ),
        ChatReactionAddedPayload(
            kind="chat.reaction.added",
            conversation_id="cnv-000001",
            chat_message_id="chm-000001",
            person_id="per-meredith-chao",
            emoji="thumbsup",
        ),
        DocumentCreatedPayload(
            kind="document.created",
            document_id="doc-000001",
            author="per-daniel-reyes",
            title="NDA Playbook",
            path="/legal/playbooks/nda-playbook.md",
            location="repository",
            content_format="markdown",
            content="# NDA Playbook\n...",
        ),
        DocumentRevisedPayload(
            kind="document.revised",
            document_id="doc-000001",
            revision=2,
            author="per-daniel-reyes",
            content="# NDA Playbook\nRevised...",
            change_summary="Added mutual-NDA guidance.",
        ),
        TicketCreatedPayload(
            kind="ticket.created",
            ticket_id="tkt-000001",
            actor="per-tom-okafor",
            title="Review Vantage NDA",
            description="Inbound NDA from vendor counsel.",
            requester="per-jess-alvarez",
            assignee="per-daniel-reyes",
            status="open",
            priority="normal",
            ticket_type="nda-review",
            fields=(),
        ),
        TicketUpdatedPayload(
            kind="ticket.updated",
            ticket_id="tkt-000001",
            actor="per-daniel-reyes",
            changes=(FieldChange(field="status", old="open", new="in-review"),),
        ),
        TicketCommentedPayload(
            kind="ticket.commented",
            ticket_id="tkt-000001",
            actor="per-daniel-reyes",
            body="Redline in progress.",
        ),
        TimeLoggedPayload(
            kind="work.time.logged",
            person_id="per-daniel-reyes",
            ticket_id="tkt-000001",
            minutes=90,
            note="NDA redline and standards review.",
            rate_cents=44_500,
            billable=True,
        ),
        CalendarEventScheduledPayload(
            kind="calendar.event.scheduled",
            calendar_event_id="cal-000001",
            organizer="per-meredith-chao",
            title="Legal stand-up",
            start=34200,
            end=35100,
            attendees=("per-meredith-chao", "per-daniel-reyes"),
            description="Daily sync.",
        ),
        CalendarEventUpdatedPayload(
            kind="calendar.event.updated",
            calendar_event_id="cal-000001",
            actor="per-meredith-chao",
            changes=(FieldChange(field="end", old="35100", new="36000"),),
        ),
        CalendarResponsePayload(
            kind="calendar.response",
            calendar_event_id="cal-000001",
            responder="per-daniel-reyes",
            response="accept",
        ),
        MeetingTranscriptPayload(
            kind="meeting.transcript",
            meeting_id="mtg-000001",
            calendar_event_id="cal-000001",
            attendees=("per-meredith-chao", "per-daniel-reyes"),
            started=34200,
            ended=35100,
            turns=(
                TranscriptTurn(speaker="per-meredith-chao", text="Morning, updates?"),
            ),
        ),
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-legal-day-1",
            seed_root=42,
            workplace_id="legal-demo",
            config_hash="0" * 64,
            schema_version=1,
            epoch="2026-03-12T00:00:00-07:00",
            timezone="America/Los_Angeles",
        ),
        SimDayStartedPayload(kind="sim.day.started", day="2026-03-12"),
        SimDayEndedPayload(kind="sim.day.ended", day="2026-03-12"),
        SimGmNotePayload(
            kind="sim.gm.note", note="Rejected intent.", rejected_intent="x"
        ),
        SimCheckpointPayload(kind="sim.checkpoint", step=12),
        SimWakePayload(kind="sim.wake", entity="daniel-reyes"),
        SimCuePayload(
            kind="sim.cue",
            entity="ravi-deshmukh",
            note="Legal turned the NDA around; send the countersigned copy.",
            topic="nda",
        ),
        SimMeetingConvenePayload(
            kind="sim.meeting.convene",
            meeting_id="mtg-000001",
            calendar_event_id="cal-000001",
            title="Legal stand-up",
            attendees=("daniel-reyes", "meredith-chao"),
            duration_seconds=900,
        ),
        SimMeetingTurnPayload(
            kind="sim.meeting.turn",
            meeting_id="mtg-000001",
            speaker="daniel-reyes",
            turn_index=0,
            attendees=("daniel-reyes", "meredith-chao"),
        ),
        SimPlanningPayload(
            kind="sim.planning",
            entity="daniel-reyes",
            day="2026-03-12",
        ),
        SimReflectionPayload(
            kind="sim.reflection",
            entity="daniel-reyes",
            day="2026-03-12",
            scope="daily",
        ),
        SimDeliverablePayload(
            kind="sim.deliverable",
            entity="daniel-reyes",
            day="2026-03-12",
        ),
        SimTimesheetPayload(
            kind="sim.timesheet",
            entity="daniel-reyes",
            day="2026-03-12",
        ),
        SimAgentMemoryPayload(
            kind="sim.agent.memory",
            note_id="mem-000001",
            entity="daniel-reyes",
            note_kind="daily_summary",
            day="2026-03-12",
            bullets=(
                MemoryBullet(
                    text="Vantage NDA needs the two-year cap",
                    importance=8,
                    refs=("thr-000001",),
                ),
            ),
            open_loops=("chase the signature packet",),
        ),
        SimAgentPlanPayload(
            kind="sim.agent.plan",
            plan_id="pln-000001",
            entity="daniel-reyes",
            day="2026-03-12",
            revision=1,
            blocks=(
                PlanBlock(
                    start=32_400,
                    end=39_600,
                    focus="NDA redline",
                    refs=("tkt-000001",),
                ),
            ),
        ),
    ]
    return {payload.kind: payload for payload in samples}

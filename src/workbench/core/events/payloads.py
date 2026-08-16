"""The closed payload union and tag registry.

Every payload kind is declared here and nowhere else. Workplaces never add
payload kinds; new kinds are additive within a schema version.
"""

from typing import Annotated

from pydantic import Field

from workbench.core.events.agent import (
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
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.meetings import (
    MeetingTranscriptPayload,
    SimMeetingConvenePayload,
    SimMeetingTurnPayload,
)
from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload

SCHEMA_VERSION = 1

EventPayload = Annotated[
    PersonRecordPayload
    | OrganizationRecordPayload
    | EmailMessagePayload
    | ChatConversationCreatedPayload
    | ChatMessagePayload
    | ChatReactionAddedPayload
    | DocumentCreatedPayload
    | DocumentRevisedPayload
    | TicketCreatedPayload
    | TicketUpdatedPayload
    | TicketCommentedPayload
    | TimeLoggedPayload
    | CalendarEventScheduledPayload
    | CalendarEventUpdatedPayload
    | CalendarResponsePayload
    | MeetingTranscriptPayload
    | SimRunStartedPayload
    | SimDayStartedPayload
    | SimDayEndedPayload
    | SimGmNotePayload
    | SimCheckpointPayload
    | SimWakePayload
    | SimAgentMemoryPayload
    | SimAgentPlanPayload
    | SimReflectionPayload
    | SimDeliverablePayload
    | SimTimesheetPayload
    | SimPlanningPayload
    | SimMeetingConvenePayload
    | SimMeetingTurnPayload
    | SimCuePayload,
    Field(discriminator="kind"),
]

TAG_REGISTRY = {
    "person.record": PersonRecordPayload,
    "org.record": OrganizationRecordPayload,
    "email.message": EmailMessagePayload,
    "chat.conversation.created": ChatConversationCreatedPayload,
    "chat.message": ChatMessagePayload,
    "chat.reaction.added": ChatReactionAddedPayload,
    "document.created": DocumentCreatedPayload,
    "document.revised": DocumentRevisedPayload,
    "ticket.created": TicketCreatedPayload,
    "ticket.updated": TicketUpdatedPayload,
    "ticket.commented": TicketCommentedPayload,
    "work.time.logged": TimeLoggedPayload,
    "calendar.event.scheduled": CalendarEventScheduledPayload,
    "calendar.event.updated": CalendarEventUpdatedPayload,
    "calendar.response": CalendarResponsePayload,
    "meeting.transcript": MeetingTranscriptPayload,
    "sim.run.started": SimRunStartedPayload,
    "sim.day.started": SimDayStartedPayload,
    "sim.day.ended": SimDayEndedPayload,
    "sim.gm.note": SimGmNotePayload,
    "sim.checkpoint": SimCheckpointPayload,
    "sim.wake": SimWakePayload,
    "sim.agent.memory": SimAgentMemoryPayload,
    "sim.agent.plan": SimAgentPlanPayload,
    "sim.reflection": SimReflectionPayload,
    "sim.deliverable": SimDeliverablePayload,
    "sim.timesheet": SimTimesheetPayload,
    "sim.planning": SimPlanningPayload,
    "sim.meeting.convene": SimMeetingConvenePayload,
    "sim.meeting.turn": SimMeetingTurnPayload,
    "sim.cue": SimCuePayload,
}

"""How long actions take: a pure function of the intent, in simulated seconds."""

from core.intents import (
    ActionIntent,
    AgentNoteIntent,
    AgentPlanIntent,
    CalendarIntent,
    ChatIntent,
    DocumentEditIntent,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
    MeetingSpeakIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
    TimesheetIntent,
)


def intent_duration(intent: ActionIntent) -> int:
    match intent:
        case EmailIntent():
            return 120 + len(intent.draft.body) // 20
        case ChatIntent():
            return 30 + len(intent.draft.body) // 30
        case TicketIntent():
            return 90
        case DocumentEditIntent():
            edit_length = len(intent.edit.new_content) if intent.edit else 0
            create_length = len(intent.create.content) if intent.create else 0
            return 600 + (edit_length + create_length) // 50
        case CalendarIntent():
            return 60
        case ReactionIntent():
            return 10
        case TimeLogIntent():
            return 60
        case TimesheetIntent():
            # Writing up the whole day: a couple of minutes plus a beat per
            # line, which is what a timesheet actually costs someone.
            return 120 + 30 * len(intent.entries)
        case IdleIntent():
            return intent.until_minutes * 60
        case AgentNoteIntent():
            # Writing the day down takes a few quiet minutes.
            return 300
        case AgentPlanIntent():
            return 300
        case MeetingSpeakIntent():
            # The cadence of a real exchange: a couple of minutes a turn.
            return 120
        case FreeformIntent():
            return 60
        case _:
            # A new intent with no duration rule used to fall through as
            # None and blow up much later inside delivery quantization,
            # with a traceback that named neither the intent nor this file.
            raise ValueError(f"no duration rule for intent kind {intent.kind!r}")

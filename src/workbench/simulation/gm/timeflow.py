"""How long actions take: a pure function of the intent, in simulated seconds."""

from workbench.core.intents import (
    ActionIntent,
    AgentNoteIntent,
    AgentPlanIntent,
    CalendarIntent,
    ChatIntent,
    DocumentEditIntent,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
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
        case IdleIntent():
            return intent.until_minutes * 60
        case AgentNoteIntent():
            # Writing the day down takes a few quiet minutes.
            return 300
        case AgentPlanIntent():
            return 300
        case FreeformIntent():
            return 60

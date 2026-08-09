"""Project chat events into the slack database."""

import sqlite3
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
from workbench.tools.slack.tables import (
    CONVERSATIONS,
    MEMBERS,
    MESSAGES,
    REACTIONS,
    ChatMessage,
    Conversation,
    Member,
    Reaction,
)


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    conversations: list[Conversation] = []
    members: list[Member] = []
    messages: list[ChatMessage] = []
    reactions: list[Reaction] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, ChatConversationCreatedPayload):
            conversations.append(
                Conversation(
                    conversation_id=payload.conversation_id,
                    name=payload.name,
                    kind=payload.conversation_type,
                    topic=payload.topic,
                    purpose=payload.purpose,
                )
            )
            members += (
                Member(conversation_id=payload.conversation_id, person_id=person)
                for person in payload.members
            )
        elif isinstance(payload, ChatMessagePayload):
            # Slack ts identity "SECONDS.MICROSECONDS": seconds are the event
            # clock; microseconds are a projection-order counter so messages
            # sharing a second keep unique, ordered timestamps.
            messages.append(
                ChatMessage(
                    chat_message_id=payload.chat_message_id,
                    conversation_id=payload.conversation_id,
                    reply_to=payload.reply_to,
                    sender=payload.sender,
                    body=payload.body,
                    time=int(event.time),
                    ts=f"{int(event.time)}.{len(messages):06d}",
                )
            )
        elif isinstance(payload, ChatReactionAddedPayload):
            reactions.append(
                Reaction(
                    conversation_id=payload.conversation_id,
                    chat_message_id=payload.chat_message_id,
                    person_id=payload.person_id,
                    emoji=payload.emoji,
                )
            )
    CONVERSATIONS.insert(connection, conversations)
    MEMBERS.insert(connection, members)
    MESSAGES.insert(connection, messages)
    REACTIONS.insert(connection, reactions)

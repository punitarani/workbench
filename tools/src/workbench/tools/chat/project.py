"""Project chat events into the chat database."""

import sqlite3
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.tools.chat.tables import (
    CONVERSATIONS,
    MEMBERS,
    MESSAGES,
    ChatMessage,
    Conversation,
    Member,
)


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    conversations: list[Conversation] = []
    members: list[Member] = []
    messages: list[ChatMessage] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, ChatConversationCreatedPayload):
            conversations.append(
                Conversation(
                    conversation_id=payload.conversation_id,
                    name=payload.name,
                    kind=payload.conversation_type,
                )
            )
            members += (
                Member(conversation_id=payload.conversation_id, person_id=person)
                for person in payload.members
            )
        elif isinstance(payload, ChatMessagePayload):
            messages.append(
                ChatMessage(
                    chat_message_id=payload.chat_message_id,
                    conversation_id=payload.conversation_id,
                    reply_to=payload.reply_to,
                    sender=payload.sender,
                    body=payload.body,
                    time=int(event.time),
                )
            )
    CONVERSATIONS.insert(connection, conversations)
    MEMBERS.insert(connection, members)
    MESSAGES.insert(connection, messages)

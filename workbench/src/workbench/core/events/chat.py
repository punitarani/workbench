from typing import Literal

from pydantic import Field, model_validator

from workbench.core.events._base import Payload
from workbench.core.ids import ChatMessageId, ConversationId, PersonId


class ChatConversationCreatedPayload(Payload):
    kind: Literal["chat.conversation.created"]
    conversation_id: ConversationId
    conversation_type: Literal["channel", "dm"]
    name: str | None
    members: tuple[PersonId, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _channels_are_named(self) -> ChatConversationCreatedPayload:
        if self.conversation_type == "channel" and not self.name:
            raise ValueError("channels must be named")
        if self.conversation_type == "dm" and self.name is not None:
            raise ValueError("dms are unnamed")
        return self


class ChatMessagePayload(Payload):
    kind: Literal["chat.message"]
    chat_message_id: ChatMessageId
    conversation_id: ConversationId
    reply_to: ChatMessageId | None
    sender: PersonId
    body: str

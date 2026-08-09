"""Row models and tables for the slack database."""

from typing import Annotated, Literal

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table


class Conversation(BaseModel):
    conversation_id: Annotated[str, Id("chat.conversation")]
    name: str | None
    kind: Literal["channel", "dm"]
    topic: str
    purpose: str


class Member(BaseModel):
    conversation_id: Annotated[str, Ref("chat.conversation")]
    person_id: Annotated[str, Ref("person")]


class ChatMessage(BaseModel):
    chat_message_id: Annotated[str, Id("chat.message")]
    conversation_id: Annotated[str, Ref("chat.conversation")]
    reply_to: Annotated[str | None, Ref("chat.message")]
    sender: Annotated[str, Ref("person")]
    body: str
    time: int
    ts: str


class Reaction(BaseModel):
    conversation_id: Annotated[str, Ref("chat.conversation")]
    chat_message_id: Annotated[str, Ref("chat.message")]
    person_id: Annotated[str, Ref("person")]
    emoji: str


CONVERSATIONS = Table("conversations", Conversation, primary_key=("conversation_id",))
MEMBERS = Table("members", Member)
MESSAGES = Table("messages", ChatMessage, primary_key=("chat_message_id",))
REACTIONS = Table("reactions", Reaction)

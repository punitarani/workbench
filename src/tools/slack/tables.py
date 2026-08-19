"""Row models and tables for the slack database."""

from typing import Annotated, Literal

from pydantic import BaseModel

from tools.db import Id, Ref, Table


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


class SentMessage(BaseModel):
    """A message the agent posted. Agent posts never join ``messages``: the
    projected tables stay the world's record, and a grader reads exactly what
    the agent said. The read tools serve both, the way Slack shows you your
    own message in the channel you posted it to."""

    sent_message_id: Annotated[str, Id("chat.message")]
    conversation_id: Annotated[str, Ref("chat.conversation")]
    reply_to: Annotated[str | None, Ref("chat.message")]
    sender: Annotated[str, Ref("person")]
    body: str
    time: int
    ts: str
    reply_broadcast: bool
    draft_id: Annotated[str | None, Ref("chat.draft")]


class MessageDraft(BaseModel):
    """A composed but unposted message. ``sent`` flips when
    ``slack_send_message`` posts it by id, so a draft cannot be sent twice."""

    draft_id: Annotated[str, Id("chat.draft")]
    conversation_id: Annotated[str, Ref("chat.conversation")]
    reply_to: Annotated[str | None, Ref("chat.message")]
    author: Annotated[str, Ref("person")]
    body: str
    time: int
    sent: bool


class ScheduledMessage(BaseModel):
    """A message queued for later. ``post_at`` is unix seconds, Slack's own
    grammar; nothing in a rollout advances far enough to deliver it."""

    scheduled_message_id: Annotated[str, Id("chat.scheduled")]
    conversation_id: Annotated[str, Ref("chat.conversation")]
    reply_to: Annotated[str | None, Ref("chat.message")]
    sender: Annotated[str, Ref("person")]
    body: str
    post_at: int
    reply_broadcast: bool


class CreatedConversation(BaseModel):
    """A channel or dm the agent opened. Members are a comma-joined list of
    person ids rather than rows, as gmail's drafts carry their addresses."""

    conversation_id: Annotated[str, Id("chat.conversation")]
    name: str | None
    kind: Literal["channel", "dm"]
    is_private: bool
    member_ids: str
    time: int


class AddedReaction(BaseModel):
    """A reaction the agent added, addressed the way the tools address a
    message: by conversation and ts, which reaches agent posts too."""

    conversation_id: Annotated[str, Ref("chat.conversation")]
    message_ts: str
    person_id: Annotated[str, Ref("person")]
    emoji: str


class Canvas(BaseModel):
    """A canvas the agent wrote. Canvases are files in Slack, so this is also
    what ``slack_read_file`` serves; sections are derived from the content."""

    canvas_id: Annotated[str, Id("chat.canvas")]
    title: str
    content: str
    owner: Annotated[str, Ref("person")]
    time: int


CONVERSATIONS = Table("conversations", Conversation, primary_key=("conversation_id",))
MEMBERS = Table("members", Member)
MESSAGES = Table("messages", ChatMessage, primary_key=("chat_message_id",))
REACTIONS = Table("reactions", Reaction)
# Action tables: empty after projection, written by the agent's tools and
# read by graders. The write aperture over a read-only record.
SENT_MESSAGES = Table("sent_messages", SentMessage, primary_key=("sent_message_id",))
MESSAGE_DRAFTS = Table("message_drafts", MessageDraft, primary_key=("draft_id",))
SCHEDULED_MESSAGES = Table(
    "scheduled_messages", ScheduledMessage, primary_key=("scheduled_message_id",)
)
CREATED_CONVERSATIONS = Table(
    "created_conversations", CreatedConversation, primary_key=("conversation_id",)
)
ADDED_REACTIONS = Table("added_reactions", AddedReaction)
CANVASES = Table("canvases", Canvas, primary_key=("canvas_id",))

"""Row models and tables for the gmail database."""

from typing import Annotated, Literal

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table


class Message(BaseModel):
    message_id: Annotated[str, Id("email.message")]
    thread_id: str
    in_reply_to: Annotated[str | None, Ref("email.message")]
    sender: Annotated[str, Ref("person")]
    subject: str
    body: str
    time: int
    snippet: str


class Recipient(BaseModel):
    message_id: Annotated[str, Ref("email.message")]
    person_id: Annotated[str, Ref("person")]
    kind: Literal["to", "cc"]


class Attachment(BaseModel):
    message_id: Annotated[str, Ref("email.message")]
    filename: str
    media_type: str
    document_id: Annotated[str, Ref("document")]


class UserLabel(BaseModel):
    """A label the agent created. System labels (INBOX, SENT, TRASH, SPAM,
    STARRED, UNREAD, IMPORTANT, DRAFT) are well-known ids, not rows."""

    label_id: Annotated[str, Id("email.label")]
    display_name: str
    text_color: str
    background_color: str


class LabelApplication(BaseModel):
    """A label applied to a message. Thread-level labelling fans out to the
    thread's messages, the way Gmail's own thread labels behave."""

    label_id: str
    message_id: Annotated[str, Ref("email.message")]


class Draft(BaseModel):
    """An unsent draft. The official Gmail MCP server has no send tool
    (ADR-0005), so this is where agent-authored mail stops."""

    draft_id: Annotated[str, Id("email.draft")]
    thread_id: str | None
    subject: str
    body: str
    html_body: str
    to_addresses: str
    cc_addresses: str
    bcc_addresses: str
    reply_to_message_id: Annotated[str | None, Ref("email.message")]
    time: int


MESSAGES = Table("messages", Message, primary_key=("message_id",))
RECIPIENTS = Table("recipients", Recipient)
ATTACHMENTS = Table("attachments", Attachment)
# Action tables: empty after projection, written by the agent's tools and
# read by graders. The mutation surface of a read-only record.
USER_LABELS = Table("user_labels", UserLabel, primary_key=("label_id",))
LABEL_APPLICATIONS = Table("label_applications", LabelApplication)
DRAFTS = Table("drafts", Draft, primary_key=("draft_id",))

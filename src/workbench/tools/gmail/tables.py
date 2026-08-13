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


MESSAGES = Table("messages", Message, primary_key=("message_id",))
RECIPIENTS = Table("recipients", Recipient)
ATTACHMENTS = Table("attachments", Attachment)

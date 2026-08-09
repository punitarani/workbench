"""Row models and tables for the matter-tracker database."""

from typing import Annotated

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table


class Ticket(BaseModel):
    ticket_id: Annotated[str, Id("ticket")]
    title: str
    description: str
    requester: Annotated[str, Ref("person")]
    assignee: Annotated[str | None, Ref("person")]
    status: str
    priority: str
    ticket_type: str
    created_time: int


class HistoryEntry(BaseModel):
    ticket_id: Annotated[str, Ref("ticket")]
    actor: Annotated[str, Ref("person")]
    field: str
    old_value: str | None
    new_value: str | None
    time: int


class Comment(BaseModel):
    ticket_id: Annotated[str, Ref("ticket")]
    actor: Annotated[str, Ref("person")]
    body: str
    time: int


TICKETS = Table("tickets", Ticket, primary_key=("ticket_id",))
HISTORY = Table("history", HistoryEntry)
COMMENTS = Table("comments", Comment)

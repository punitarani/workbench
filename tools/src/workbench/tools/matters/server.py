"""Read tools over the matter-tracker database."""

from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.db import Query, connect_readonly
from workbench.tools.framework import UnknownRefError
from workbench.tools.matters.tables import TICKETS, Ticket


class HistoryView(BaseModel):
    actor: str
    field: str
    old_value: str | None
    new_value: str | None
    time: int


class CommentView(BaseModel):
    actor: str
    body: str
    time: int


class TicketView(Ticket):
    history: tuple[HistoryView, ...]
    comments: tuple[CommentView, ...]


TICKET_HISTORY = Query(
    HistoryView,
    "SELECT actor, field, old_value, new_value, time FROM history "
    "WHERE ticket_id=? ORDER BY time",
)

TICKET_COMMENTS = Query(
    CommentView,
    "SELECT actor, body, time FROM comments WHERE ticket_id=? ORDER BY time",
)


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_tickets(status: str | None = None) -> list[dict]:
        """List matters, optionally filtered by status."""
        with connect_readonly(db_path) as connection:
            where = {"status": status} if status is not None else None
            tickets = TICKETS.select(connection, where=where, order_by="created_time")
            return [t.model_dump() for t in tickets]

    @server.tool()
    def read_ticket(ticket_id: str) -> dict:
        """Read one matter with its full history and comments."""
        with connect_readonly(db_path) as connection:
            tickets = TICKETS.select(connection, where={"ticket_id": ticket_id})
            if not tickets:
                raise UnknownRefError(f"no ticket {ticket_id}")
            view = TicketView(
                **tickets[0].model_dump(),
                history=tuple(TICKET_HISTORY.run(connection, ticket_id)),
                comments=tuple(TICKET_COMMENTS.run(connection, ticket_id)),
            )
            return view.model_dump()

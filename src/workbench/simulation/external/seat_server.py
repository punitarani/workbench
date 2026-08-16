"""The agent-facing MCP surface over an interactive seat.

Everything the agent sees is rendered data: event payloads plus sim time,
never engine envelopes (seq, source, causality) and never ``sim.*`` events.
The write tools submit typed intents; the game master grounds or rejects
them exactly as it would a persona's — the seat is not trusted.
"""

from mcp.server import MCPServer

from workbench.core.actions import IntentAction
from workbench.core.events import Event
from workbench.core.events.tickets import FieldChange
from workbench.core.intents import (
    ChatDraft,
    ChatIntent,
    DocumentCreateSpec,
    DocumentEdit,
    DocumentEditIntent,
    EmailDraft,
    EmailIntent,
    IdleIntent,
    TicketCreateSpec,
    TicketIntent,
)
from workbench.simulation.external.session import SeatSession


def _render(event: Event) -> dict:
    return {"time": int(event.time), **event.payload.model_dump(mode="json")}


def build_seat_server(session: SeatSession) -> MCPServer:
    server = MCPServer(
        name="workbench-seat",
        instructions=(
            "Your seat in the organization. Call await_turn to receive your "
            "next working turn with its new observations, then answer with "
            "exactly one action tool: send_email, send_chat, create_ticket, "
            "update_ticket, edit_document, create_document, or idle."
        ),
    )

    @server.tool()
    async def await_turn() -> dict:
        """Wait for your next turn; returns new observations and the call
        to action, or day_over when the working day has ended."""
        turn = await session.next_turn()
        if turn is None:
            return {"day_over": True}
        return {
            "time": int(turn.time),
            "call_to_action": turn.spec.call_to_action,
            "observations": [
                _render(event)
                for event in turn.observations
                if not event.tag.startswith("sim.")
            ],
        }

    @server.tool()
    def send_email(
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        thread_ref: str | None = None,
        reply_to_ref: str | None = None,
        attach_document_refs: list[str] | None = None,
    ) -> dict:
        """Send an email; recipients by full name from the directory."""
        session.submit(
            IntentAction(
                intent=EmailIntent(
                    thread_ref=thread_ref,
                    reply_to_ref=reply_to_ref,
                    draft=EmailDraft(
                        to=tuple(to),
                        cc=tuple(cc or ()),
                        subject=subject,
                        body=body,
                        summary=subject,
                    ),
                    attach_document_refs=tuple(attach_document_refs or ()),
                )
            )
        )
        return {"submitted": "email"}

    @server.tool()
    def send_chat(
        conversation_ref: str, body: str, reply_to_ref: str | None = None
    ) -> dict:
        """Post a chat message to a channel or direct conversation."""
        session.submit(
            IntentAction(
                intent=ChatIntent(
                    conversation_ref=conversation_ref,
                    reply_to_ref=reply_to_ref,
                    draft=ChatDraft(body=body, summary=body[:80]),
                )
            )
        )
        return {"submitted": "chat"}

    @server.tool()
    def create_ticket(
        title: str,
        description: str,
        requester: str,
        status: str,
        priority: str,
        ticket_type: str,
        assignee: str | None = None,
    ) -> dict:
        """Open a ticket; people by full name, vocabulary per the workplace."""
        session.submit(
            IntentAction(
                intent=TicketIntent(
                    ticket_ref=None,
                    create=TicketCreateSpec(
                        title=title,
                        description=description,
                        requester_ref=requester,
                        assignee_ref=assignee,
                        status=status,
                        priority=priority,
                        ticket_type=ticket_type,
                    ),
                )
            )
        )
        return {"submitted": "ticket"}

    @server.tool()
    def update_ticket(
        ticket_ref: str,
        field: str | None = None,
        old: str | None = None,
        new: str | None = None,
        comment: str | None = None,
    ) -> dict:
        """Change one ticket field and/or add a comment."""
        changes = (
            (FieldChange(field=field, old=old, new=new),) if field is not None else ()
        )
        session.submit(
            IntentAction(
                intent=TicketIntent(
                    ticket_ref=ticket_ref, changes=changes, comment=comment
                )
            )
        )
        return {"submitted": "ticket"}

    @server.tool()
    def edit_document(document_ref: str, new_content: str, change_summary: str) -> dict:
        """Revise an existing document."""
        session.submit(
            IntentAction(
                intent=DocumentEditIntent(
                    document_ref=document_ref,
                    edit=DocumentEdit(
                        new_content=new_content, change_summary=change_summary
                    ),
                )
            )
        )
        return {"submitted": "document_edit"}

    @server.tool()
    def create_document(
        title: str, path: str, content: str, content_format: str = "markdown"
    ) -> dict:
        """Create a new document in the repository.

        `content_format` is one of markdown, formatted (a .docx or .pdf),
        spreadsheet (a .xlsx), or slides (a .pptx); anything but markdown
        expects the structured JSON for that form.
        """

        session.submit(
            IntentAction(
                intent=DocumentEditIntent(
                    document_ref=None,
                    create=DocumentCreateSpec(
                        title=title,
                        path=path,
                        content=content,
                        content_format=content_format,
                    ),
                )
            )
        )
        return {"submitted": "document_create"}

    @server.tool()
    def idle(minutes: int = 30) -> dict:
        """Do nothing until your next check-in."""
        session.submit(IntentAction(intent=IdleIntent(until_minutes=minutes)))
        return {"submitted": "idle"}

    return server

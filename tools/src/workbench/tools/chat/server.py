"""Read tools over the chat database."""

from pathlib import Path

from mcp.server import MCPServer

from workbench.tools.chat.tables import (
    CONVERSATIONS,
    MEMBERS,
    MESSAGES,
    ChatMessage,
    Conversation,
)
from workbench.tools.db import Query, connect_readonly
from workbench.tools.framework import UnknownRefError


class ConversationView(Conversation):
    members: tuple[str, ...]


SEARCH = Query(ChatMessage, "SELECT * FROM messages WHERE body LIKE ? ORDER BY time")


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_conversations() -> list[dict]:
        """List channels and direct-message conversations with members."""
        with connect_readonly(db_path) as connection:
            views = []
            for conversation in CONVERSATIONS.select(
                connection, order_by="conversation_id"
            ):
                members = MEMBERS.select(
                    connection,
                    where={"conversation_id": conversation.conversation_id},
                )
                views.append(
                    ConversationView(
                        **conversation.model_dump(),
                        members=tuple(m.person_id for m in members),
                    ).model_dump()
                )
            return views

    @server.tool()
    def read_conversation(conversation_id: str) -> list[dict]:
        """Read a conversation's messages, oldest first."""
        with connect_readonly(db_path) as connection:
            known = CONVERSATIONS.select(
                connection, where={"conversation_id": conversation_id}
            )
            if not known:
                raise UnknownRefError(f"no conversation {conversation_id}")
            messages = MESSAGES.select(
                connection, where={"conversation_id": conversation_id}, order_by="time"
            )
            return [m.model_dump() for m in messages]

    @server.tool()
    def search_chat(query: str) -> list[dict]:
        """Search message bodies across conversations."""
        with connect_readonly(db_path) as connection:
            return [m.model_dump() for m in SEARCH.run(connection, f"%{query}%")]

"""Chat: conversations, members, and messages become chat.db and its tools."""

from workbench.tools.chat.project import project
from workbench.tools.chat.server import register
from workbench.tools.chat.tables import CONVERSATIONS, MEMBERS, MESSAGES
from workbench.tools.framework import ToolSystem

SYSTEM = ToolSystem(
    name="chat",
    handled_tags=("chat.conversation.created", "chat.message", "person.record"),
    tables=(CONVERSATIONS, MEMBERS, MESSAGES),
    project=project,
    register=register,
)

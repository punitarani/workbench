"""Slack: chat events served under Slack's official MCP tool names."""

from workbench.tools.framework import ToolSystem
from workbench.tools.slack.project import project
from workbench.tools.slack.server import register
from workbench.tools.slack.tables import CONVERSATIONS, MEMBERS, MESSAGES, REACTIONS

SYSTEM = ToolSystem(
    name="slack",
    handled_tags=(
        "chat.conversation.created",
        "chat.message",
        "chat.reaction.added",
        "person.record",
    ),
    tables=(CONVERSATIONS, MEMBERS, MESSAGES, REACTIONS),
    project=project,
    register=register,
    directory_tool=False,
)

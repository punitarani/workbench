"""Slack: chat events served under Slack's official MCP tool names."""

from workbench.tools.framework import ToolSystem
from workbench.tools.slack.project import project
from workbench.tools.slack.server import register
from workbench.tools.slack.tables import (
    ADDED_REACTIONS,
    CANVASES,
    CONVERSATIONS,
    CREATED_CONVERSATIONS,
    MEMBERS,
    MESSAGE_DRAFTS,
    MESSAGES,
    REACTIONS,
    SCHEDULED_MESSAGES,
    SENT_MESSAGES,
)

SYSTEM = ToolSystem(
    name="slack",
    handled_tags=(
        "chat.conversation.created",
        "chat.message",
        "chat.reaction.added",
        "person.record",
    ),
    tables=(
        CONVERSATIONS,
        MEMBERS,
        MESSAGES,
        REACTIONS,
        SENT_MESSAGES,
        MESSAGE_DRAFTS,
        SCHEDULED_MESSAGES,
        CREATED_CONVERSATIONS,
        ADDED_REACTIONS,
        CANVASES,
    ),
    project=project,
    register=register,
    directory_tool=False,
)

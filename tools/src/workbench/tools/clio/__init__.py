"""Clio practice management: matters, contacts, activities, notes, and time
entries become clio.db, read through Clio Manage API v4 shapes."""

from workbench.tools.clio.project import project
from workbench.tools.clio.server import register
from workbench.tools.clio.tables import (
    ACTIVITIES,
    MATTER_HISTORY,
    MATTERS,
    NOTES,
    ORGANIZATIONS,
)
from workbench.tools.framework import ToolSystem

SYSTEM = ToolSystem(
    name="clio",
    handled_tags=(
        "ticket.created",
        "ticket.updated",
        "ticket.commented",
        "work.time.logged",
        "org.record",
        "person.record",
    ),
    tables=(MATTERS, MATTER_HISTORY, NOTES, ACTIVITIES, ORGANIZATIONS),
    project=project,
    register=register,
    directory_tool=False,
)

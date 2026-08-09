"""Matter tracker: folded ticket state plus complete history become matters.db."""

from workbench.tools.framework import ToolSystem
from workbench.tools.matters.project import project
from workbench.tools.matters.server import register
from workbench.tools.matters.tables import COMMENTS, HISTORY, TICKETS

SYSTEM = ToolSystem(
    name="matters",
    handled_tags=(
        "ticket.created",
        "ticket.updated",
        "ticket.commented",
        "person.record",
    ),
    tables=(TICKETS, HISTORY, COMMENTS),
    project=project,
    register=register,
)

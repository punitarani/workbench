"""Gmail: the world log's email events become gmail.db and its read tools."""

from workbench.tools.framework import ToolSystem
from workbench.tools.gmail.project import project
from workbench.tools.gmail.server import register
from workbench.tools.gmail.tables import ATTACHMENTS, MESSAGES, RECIPIENTS

SYSTEM = ToolSystem(
    name="gmail",
    handled_tags=("email.message", "person.record"),
    tables=(MESSAGES, RECIPIENTS, ATTACHMENTS),
    project=project,
    register=register,
    directory_tool=False,
)

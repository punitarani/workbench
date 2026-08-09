"""Mail: the world log's email events become mail.db and its read tools."""

from workbench.tools.framework import ToolSystem
from workbench.tools.mail.project import project
from workbench.tools.mail.server import register
from workbench.tools.mail.tables import ATTACHMENTS, MESSAGES, RECIPIENTS

SYSTEM = ToolSystem(
    name="mail",
    handled_tags=("email.message", "person.record"),
    tables=(MESSAGES, RECIPIENTS, ATTACHMENTS),
    project=project,
    register=register,
)

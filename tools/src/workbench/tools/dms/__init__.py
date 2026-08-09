"""Document repository: documents and full revision history become dms.db."""

from workbench.tools.dms.project import project
from workbench.tools.dms.server import register
from workbench.tools.dms.tables import DOCUMENTS, REVISIONS
from workbench.tools.framework import ToolSystem

SYSTEM = ToolSystem(
    name="dms",
    handled_tags=("document.created", "document.revised", "person.record"),
    tables=(DOCUMENTS, REVISIONS),
    project=project,
    register=register,
)

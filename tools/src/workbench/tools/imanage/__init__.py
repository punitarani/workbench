"""iManage work product: documents and versions become imanage.db.

Mirrors the official iManage MCP server (GA May 2026): one "LEGAL"
library, Work API display ids "LEGAL!{number}.{version}", workspaces
derived from top-level path segments, profile-shaped JSON responses.
"""

from workbench.tools.framework import ToolSystem
from workbench.tools.imanage.project import project
from workbench.tools.imanage.server import register
from workbench.tools.imanage.tables import DOCUMENTS, VERSIONS

SYSTEM = ToolSystem(
    name="imanage",
    handled_tags=("document.created", "document.revised", "person.record"),
    tables=(DOCUMENTS, VERSIONS),
    project=project,
    register=register,
    directory_tool=False,
)

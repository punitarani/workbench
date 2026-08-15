"""iManage work product: documents and versions become imanage.db.

Mirrors the official iManage Work MCP connector (GA May 2026): one
"LEGAL" library, Work API display ids "LEGAL!{number}.{version}",
workspaces derived from top-level path segments, profile-shaped JSON
responses. The actions table is the one table the projection leaves
empty: the tools write it as the agent opens documents and matters, and
the recents and the actions panel read it back.
"""

from workbench.tools.framework import ToolSystem
from workbench.tools.imanage.project import project
from workbench.tools.imanage.server import register
from workbench.tools.imanage.tables import ACTIONS, DOCUMENTS, VERSIONS

SYSTEM = ToolSystem(
    name="imanage",
    handled_tags=("document.created", "document.revised", "person.record"),
    tables=(DOCUMENTS, VERSIONS, ACTIONS),
    project=project,
    register=register,
    directory_tool=False,
)

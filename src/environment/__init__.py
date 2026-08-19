"""Environment assembly: turning a world log into an environment bundle —
projected tool databases and server wiring offstage, the agent's own
document workspace onstage.
"""

from environment.materialize import (
    AGENT_WORKSPACE,
    MaterializedEnvironment,
    materialize,
)

__all__ = ["AGENT_WORKSPACE", "MaterializedEnvironment", "materialize"]

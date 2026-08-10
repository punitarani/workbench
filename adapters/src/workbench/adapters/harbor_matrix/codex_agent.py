from harbor.agents.installed.base import CliFlag
from harbor.agents.installed.codex import Codex


class HartwellCodex(Codex):
    """Codex with local compaction for third-party Responses providers."""

    CLI_FLAGS = [
        *Codex.CLI_FLAGS,
        CliFlag(
            "compaction_mode",
            cli="--disable",
            type="enum",
            choices=["local"],
            default="local",
            format="--disable remote_compaction_v2",
        ),
    ]

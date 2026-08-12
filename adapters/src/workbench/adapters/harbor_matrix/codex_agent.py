import json
import shlex
from typing import Any

from harbor.agents.installed.base import BaseEnvironment, CliFlag
from harbor.agents.installed.codex import Codex

# Models whose tool calls Codex's unified_exec router rejects. GPT-5.6 Sol
# emits an ``exec`` payload the router aborts on ("tool exec invoked with
# incompatible payload"), so every Sol cell failed before touching a tool
# while the model's own transcript showed it understood the task exactly.
# Removing ``--enable unified_exec`` falls Codex back to its standard shell
# tool, which Sol drives fine. Opus tolerates unified_exec and its scores
# were measured with it, so it is deliberately NOT in this set -- changing
# a working model's harness would void its numbers.
_NO_UNIFIED_EXEC = ("gpt-5.6-sol", "sol")
_UNIFIED_EXEC_FLAG = "--enable unified_exec "


class HartwellCodex(Codex):
    """Codex with local compaction for third-party Responses providers."""

    CLI_FLAGS = [
        *Codex.CLI_FLAGS,
        CliFlag(
            "compaction_mode",
            cli="--disable",
            type="enum",
            choices=["custom-provider-local"],
            default="custom-provider-local",
            format="--disable remote_compaction_v2",
        ),
    ]

    def _uses_unified_exec(self) -> bool:
        model = (self.model_name or "").lower()
        return not any(token in model for token in _NO_UNIFIED_EXEC)

    async def exec_as_agent(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        # The launch command hardcodes --enable unified_exec for every model.
        # Drop it for the models whose router rejects that tool, and only for
        # the actual `codex exec` invocation so setup steps are untouched.
        if (
            not self._uses_unified_exec()
            and "codex exec " in command
            and _UNIFIED_EXEC_FLAG in command
        ):
            command = command.replace(_UNIFIED_EXEC_FLAG, "", 1)
        return await super().exec_as_agent(
            environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec
        )

    def _get_env(self, key: str) -> str | None:
        if key == "OPENAI_API_KEY":
            if gateway_token := super()._get_env("HARTWELL_GATEWAY_TOKEN"):
                return gateway_token
        return super()._get_env(key)

    def build_cli_flags(self) -> str:
        base_url = super()._get_env("OPENAI_BASE_URL")
        if not base_url:
            raise ValueError("Hartwell Codex requires OPENAI_BASE_URL")
        provider_flags = (
            "-c model_provider=hartwell_gateway",
            "-c model_providers.hartwell_gateway.name=hartwell_gateway",
            "-c "
            + shlex.quote(
                "model_providers.hartwell_gateway.base_url=" + json.dumps(base_url)
            ),
            "-c model_providers.hartwell_gateway.env_key=OPENAI_API_KEY",
            "-c model_providers.hartwell_gateway.wire_api=responses",
            "-c model_providers.hartwell_gateway.requires_openai_auth=false",
            "-c model_providers.hartwell_gateway.supports_websockets=false",
        )
        return " ".join((super().build_cli_flags(), *provider_flags))

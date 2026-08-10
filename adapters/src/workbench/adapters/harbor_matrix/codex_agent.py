import json
import shlex

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
            choices=["custom-provider-local"],
            default="custom-provider-local",
            format="--disable remote_compaction_v2",
        ),
    ]

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

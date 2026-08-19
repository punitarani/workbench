from typing import Any

from harbor.agents.installed.base import BaseEnvironment
from harbor.agents.installed.opencode import OpenCode

HARTWELL_OPENCODE_IMPORT_PATH = "adapters.harbor_matrix.opencode_agent:HartwellOpencode"


class HartwellOpencode(OpenCode):
    """OpenCode routed through the Hartwell provider gateway.

    Opencode's ``openai`` provider reads ``OPENAI_API_KEY`` from the
    environment and ``baseURL`` from ``~/.config/opencode/opencode.json``
    (which the base agent writes). The container is handed the gateway's
    bearer token as ``HARTWELL_GATEWAY_TOKEN`` via ``--env-file``; expose it
    under the key opencode reads so the request carries the right credential
    -- as :class:`HartwellCodex` does.

    Harbor's ``OpenCode.run`` builds the CLI for an older opencode
    (``opencode --model=X run ... --thinking --dangerously-skip-permissions``).
    The installed opencode CLI dropped those flags and moved ``--model`` under
    the ``run`` subcommand, so that invocation just prints help and exits 1.
    ``exec_as_agent`` rewrites the one ``opencode ... run`` line to the current
    CLI shape; every other exec (setup, config, skills) passes through
    untouched. Permissions are granted in the config instead of on the command
    line, so tools run without prompting in the non-interactive ``run`` mode.
    """

    # Merged first by the base config builder. Grant the tool categories the
    # audit needs so opencode does not block on an approval prompt it cannot
    # answer without a TTY.
    _DEFAULT_CONFIG: dict[str, Any] = {
        "permission": {"edit": "allow", "bash": "allow", "webfetch": "allow"}
    }

    def _get_env(self, key: str) -> str | None:
        if key == "OPENAI_API_KEY":
            if gateway_token := super()._get_env("HARTWELL_GATEWAY_TOKEN"):
                return gateway_token
        return super()._get_env(key)

    def _rewrite_opencode_command(self, command: str) -> str:
        model = self.model_name
        old = f"opencode --model={model} run"
        new = f"opencode run --model={model}"
        if old not in command:
            return command
        command = command.replace(old, new, 1)
        return command.replace(" --thinking --dangerously-skip-permissions", "", 1)

    async def exec_as_agent(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        if "opencode --model=" in command and " run " in command:
            command = self._rewrite_opencode_command(command)
            # OpenCode.run reads OPENAI_API_KEY / OPENAI_BASE_URL from
            # os.environ, missing Harbor's --env-file / --ae (which land in
            # _extra_env), so its openai provider raised ProviderAuthError.
            # Inject both into the container env from _extra_env: the gateway
            # bearer token as the key, and the gateway URL as the base so the
            # openai provider talks to the gateway, not api.openai.com.
            env = dict(env or {})
            if token := self._get_env("HARTWELL_GATEWAY_TOKEN"):
                env["OPENAI_API_KEY"] = token
            if base_url := self._get_env("OPENAI_BASE_URL"):
                env["OPENAI_BASE_URL"] = base_url
        return await super().exec_as_agent(
            environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec
        )

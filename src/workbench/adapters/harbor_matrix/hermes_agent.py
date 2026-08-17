"""Hermes through the Hartwell gateway, installed so a sandbox can survive it.

This harness exists for one model. GPT-5.6 Sol cannot be measured on the
Ashgrove suite through either of the others:

* **codex** aborts every call with ``tool exec invoked with incompatible
  payload`` and never reaches an MCP server. Dropping ``--enable
  unified_exec`` (which fixed Sol on Hartwell) does not help here, and the
  model's own reasoning says why: it emits ``functions.functions__exec``,
  a double-prefixed tool name that codex's router cannot resolve.
* **opencode** dies on the first tool round-trip with a 400 from Azure,
  ``No tool call found for function call output with call_id ...``.

Neither is the model's doing. Driven directly, ``openai/gpt-5.6-sol``
completes a full two-turn tool round-trip on *both* the chat-completions
and responses APIs — checked against the same provider the harness uses.
So a third opinion is the only way to find out what Sol actually scores,
and a score of 0.000 from a harness that never reached a tool is not a
measurement of anything.

The install needs help. Harbor runs the upstream ``install.sh`` as the
*agent* user under ``set -euo pipefail``, and the script's default path
wants to apt-get ffmpeg (which a non-root user cannot do) and to fetch
Playwright/Chromium and the computer-use driver (which a host allowlist
will not permit). Any one of those is fatal to the whole chain. The
overridden install skips the three, and pre-installs as root the packages
the script would otherwise reach for.
"""

import yaml
from harbor.agents.installed.base import BaseEnvironment
from harbor.agents.installed.hermes import Hermes

HARTWELL_HERMES_IMPORT_PATH = (
    "workbench.adapters.harbor_matrix.hermes_agent:HartwellHermes"
)

_INSTALLER = (
    "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh"
)


class HartwellHermes(Hermes):
    """Hermes with a sandbox-survivable install.

    The gateway needs no credential plumbing here, unlike
    :class:`HartwellCodex` and :class:`HartwellOpencode`: Hermes' ``openai``
    provider reads ``OPENAI_API_KEY`` and ``OPENAI_BASE_URL`` straight off
    the host environment and forwards them into the container, and
    ``run_rollouts._run_one`` sets both to the gateway.
    """

    @staticmethod
    def _build_config_yaml(model: str) -> str:
        """The same config, but naming the provider instead of guessing.

        Harbor hardcodes ``provider: auto``. With a slashed model id that
        resolves to OpenRouter, so hermes reached past the gateway to
        OpenRouter directly with no key of its own and came back
        ``HTTP 401: Missing Authentication header`` -- an error from
        OpenRouter, not from us; the gateway's own refusal reads
        ``unauthorized``.

        Naming ``openai`` puts it on the native path, which is the one that
        reads ``OPENAI_API_KEY`` and ``OPENAI_BASE_URL`` -- both of which
        ``run_rollouts._run_one`` points at the gateway.

        ``openrouter`` rather than ``openai``: hermes rejects the latter
        outright ("Unknown provider 'openai'"), and the gateway is an
        OpenRouter proxy anyway -- same wire format, same model ids, so
        the alias table resolves ``openai/gpt-5.6-sol`` and applies its
        provider pins exactly as it does for the other two harnesses.
        """

        loaded = yaml.safe_load(Hermes._build_config_yaml(model))
        loaded["provider"] = "openrouter"
        return yaml.dump(loaded, default_flow_style=False)

    async def exec_as_agent(  # type: ignore[override]
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ):
        """Hand the gateway to hermes under the names it reads.

        Harbor decides which credentials to forward from the model id's
        prefix: ``openai/...`` takes the native branch and sets
        ``OPENAI_API_KEY``/``OPENAI_BASE_URL``. But the config names
        ``openrouter`` as the provider, and that provider reads
        ``OPENROUTER_*``. Without this the request left the container with
        no credential at all and OpenRouter answered ``HTTP 401: Missing
        Authentication header`` -- its error, not the gateway's, which
        would have said ``unauthorized``.
        """

        merged = dict(env or {})
        for source, target in (
            ("OPENAI_API_KEY", "OPENROUTER_API_KEY"),
            ("OPENAI_BASE_URL", "OPENROUTER_BASE_URL"),
        ):
            value = merged.get(source) or self._get_env(source)
            if value:
                merged.setdefault(target, value)
        return await super().exec_as_agent(
            environment, command, env=merged, cwd=cwd, timeout_sec=timeout_sec
        )

    async def install(self, environment: BaseEnvironment) -> None:
        # ffmpeg and the rest as root, so the installer finds them present
        # and never tries apt as the agent user.
        await self.exec_as_root(
            environment,
            command=(
                "apt-get update && apt-get install -y "
                "curl git ripgrep xz-utils ffmpeg"
            ),
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        branch = f" --branch {self._version}" if self._version else ""
        # As root, deliberately. Run as the agent user the installer wants
        # apt for anything missing and cannot have it, and it lands the
        # code under a home directory; as root it installs to
        # /usr/local/lib/hermes-agent and links the binary into
        # /usr/local/bin, which is on every user's PATH. Verified both ways
        # in the task image: root exits 0, agent does not.
        await self.exec_as_root(
            environment,
            command=(
                "set -euo pipefail; "
                f"curl -fsSL {_INSTALLER} | bash -s -- "
                # Browser and computer-use pull Chromium and a driver from
                # hosts no task allowlist has, and this suite needs neither:
                # every fact it grades arrives over MCP or off the disk.
                f"--skip-setup --skip-browser --skip-computer-use{branch} && "
                'export PATH="$HOME/.local/bin:$PATH" && '
                'export HERMES_HOME="${HERMES_HOME:-/tmp/hermes}" && '
                'mkdir -p "$HERMES_HOME" "$HERMES_HOME/sessions" '
                '"$HERMES_HOME/skills" "$HERMES_HOME/memories" && '
                "hermes version && "
                # Last, not before `hermes version`: installing as root
                # leaves HERMES_HOME root-owned, and running the binary
                # once as root mints more of it (`logs/curator`). Harbor
                # then writes config.yaml and the agent runs the tool, both
                # as `agent` -- so the chown has to come after everything
                # root does, or the next permission error is just further
                # down the tree. The code stays root-owned in
                # /usr/local/lib; only the data directory changes hands.
                'chown -R agent:agent "$HERMES_HOME"'
            ),
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )

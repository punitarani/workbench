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

HARTWELL_HERMES_IMPORT_PATH = "adapters.harbor_matrix.hermes_agent:HartwellHermes"

_INSTALLER = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh"


class HartwellHermes(Hermes):
    """Hermes with a sandbox-survivable install.

    The gateway needs no credential plumbing here, unlike
    :class:`HartwellCodex` and :class:`HartwellOpencode`: Hermes' ``openai``
    provider reads ``OPENAI_API_KEY`` and ``OPENAI_BASE_URL`` straight off
    the host environment and forwards them into the container, and
    ``run_rollouts._run_one`` sets both to the gateway.
    """

    def _build_config_yaml(self, model: str) -> str:  # type: ignore[override]
        """Put the gateway in the *config*, not only in the environment.

        Harbor hardcodes ``provider: auto`` and writes the endpoint nowhere
        -- it forwards ``OPENAI_BASE_URL`` only on the native ``openai``
        branch (``harbor/agents/installed/hermes.py``), and our provider is
        not that branch. ``exec_as_agent`` below supplies both names in the
        environment, and that is enough for the *main* agent.

        It is not enough for the agent's sub-agents, and that distinction
        cost three sweeps. A gpt-5.6-sol trial's log showed the main agent
        planning the task correctly and dispatching eight sub-tasks, each
        of which "completed" in 0.7-2.4s:

            [subagent-2] Provider: openrouter  Model: openai/gpt-5.6-sol
            [subagent-2] Endpoint: https://openrouter.ai/api/v1
            [subagent-2] HTTP 401: Missing Authentication header

        Eighty such lines, every one of them from a ``[subagent-N]`` and
        none from the main agent. *Missing*, not rejected: the sub-agent
        sent no ``Authorization`` header at all, so it had neither the
        endpoint nor the token. Sub-agents rebuild their client from
        ``config.yaml`` -- which is how they knew the provider and the
        model -- and that file named no endpoint and carried no key.

        So the credential and its endpoint go in the file. Hermes reads
        both off the ``model`` mapping, and reads them *only* under
        ``provider: custom``:

          * ``agent/credential_sources.py`` documents the source list as
            ``model_config -- model.api_key when model.provider ==
            "custom"``. Under any other provider the key is ignored.
          * ``hermes_cli/runtime_provider.py``'s
            ``_config_base_url_trustworthy_for_bare_custom`` rejects a
            non-loopback ``model.base_url`` unless the configured provider
            is already ``custom`` -- guarding against a stale URL hijacking
            a local session. ``host.docker.internal`` is not loopback, so
            without ``custom`` the endpoint would be dropped on the floor
            exactly as it was.

        ``api_mode`` is pinned rather than inferred: hermes derives it from
        the host, and only an OpenAI host implies the Responses API. This
        one is ``host.docker.internal``, so it would infer chat completions
        anyway -- but ``gateway.py`` serves ``/v1/chat/completions`` and
        ``/v1/responses`` and nothing else, and an inference that changes
        under us takes the whole tier to 0.000 without saying why.

        The environment is still set, and deliberately: it costs nothing
        and it is what the main agent used successfully all along.
        """

        loaded = yaml.safe_load(Hermes._build_config_yaml(model))
        base = self._get_env("OPENAI_BASE_URL")
        token = self._get_env("HARTWELL_GATEWAY_TOKEN")
        if not (base and token):
            # Not a rollout through our gateway -- leave harbor's own
            # config alone rather than writing a half-formed custom
            # provider that would fail further downstream and less
            # legibly.
            loaded["provider"] = "openrouter"
            return yaml.dump(loaded, default_flow_style=False)
        loaded["provider"] = "custom"
        loaded["model"] = {
            "provider": "custom",
            "default": model,
            "base_url": base,
            "api_key": token,
            "api_mode": "chat_completions",
        }
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
            # The gateway token first, because nothing sets
            # `OPENAI_API_KEY` for this agent. Codex reaches the same place
            # by overriding `_get_env` to answer `OPENAI_API_KEY` with the
            # gateway token; hermes had the mapping below and no such
            # override, so it mapped a variable that was never populated
            # and the container reached the gateway carrying whatever
            # `OPENROUTER_API_KEY` the host had exported — a real
            # OpenRouter key, which the gateway is not. `gateway.py`
            # answers a Bearer mismatch with exactly `401 unauthorized`,
            # which is what every trial got.
            ("OPENAI_API_KEY", "OPENROUTER_API_KEY"),
            ("OPENAI_BASE_URL", "OPENROUTER_BASE_URL"),
        ):
            value = merged.get(source) or self._get_env(source)
            if value:
                merged.setdefault(target, value)
        # The gateway token *overwrites*, and that distinction is the whole
        # fix. Everything above uses `setdefault`, which is right for a
        # fallback and wrong for a credential: the container already
        # carries whatever `OPENROUTER_API_KEY` the host exported — a real
        # OpenRouter key — so a `setdefault` here is a no-op and hermes
        # presents the wrong bearer to a gateway that is not OpenRouter.
        # `gateway.py` answers a mismatch with exactly `401 unauthorized`,
        # which is what every trial got, install bug or no install bug.
        #
        # Codex reaches the same place differently, by overriding
        # `_get_env` so that a request for `OPENAI_API_KEY` returns the
        # gateway token. Hermes has no such override, so it is done here.
        if token := (
            merged.get("HARTWELL_GATEWAY_TOKEN")
            or self._get_env("HARTWELL_GATEWAY_TOKEN")
        ):
            merged["OPENROUTER_API_KEY"] = token
            merged["OPENAI_API_KEY"] = token
        # And the ENDPOINT, by the same rule and for the same reason. The
        # mapping above uses `setdefault`, which is a no-op whenever
        # `OPENROUTER_BASE_URL` is already present and silent when
        # `OPENAI_BASE_URL` is absent -- and one trial's log showed the
        # result: 32 mentions of `https://openrouter.ai/api/v1`, **zero**
        # of the gateway, and 64 `HTTP 401: Missing Authentication header`.
        # The whole run, main agent included, went to the real provider
        # with no credential. Its eight sub-tasks each "completed" in under
        # three seconds, which is what a failing call looks like from
        # outside, and the trial scored 0.000 three times over while
        # appearing to work.
        #
        # A credential and its endpoint are one setting. Set them the same
        # way, and never with `setdefault`.
        if base := (merged.get("OPENAI_BASE_URL") or self._get_env("OPENAI_BASE_URL")):
            merged["OPENROUTER_BASE_URL"] = base
            merged["OPENAI_BASE_URL"] = base
        return await super().exec_as_agent(
            environment, command, env=merged, cwd=cwd, timeout_sec=timeout_sec
        )

    async def install(self, environment: BaseEnvironment) -> None:
        # ffmpeg and the rest as root, so the installer finds them present
        # and never tries apt as the agent user.
        await self.exec_as_root(
            environment,
            command=(
                "apt-get update && apt-get install -y curl git ripgrep xz-utils ffmpeg"
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
                # `--version`, not `version`. Upstream removed the
                # subcommand in v0.20.5 (2026.8.19) and argparse answers an
                # unknown one with a usage message and a non-zero exit, so
                # this line — a liveness check appended *after* a
                # successful install — took the whole agent setup down.
                # Every gpt-5.6-sol trial errored rather than scored, two
                # days after the same path last worked.
                #
                # It cost a while to find because the installer exits 0 on
                # its own: reproducing the failure needed the command that
                # runs *after* it, and Harbor truncates the middle of a
                # captured stdout, so the usage message was never visible.
                "hermes --version && "
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

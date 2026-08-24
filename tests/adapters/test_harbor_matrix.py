import asyncio
import json
import logging
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from adapters.harbor_matrix import provenance as matrix_provenance
from adapters.harbor_matrix import runner as matrix_runner
from adapters.harbor_matrix.cli import parse_args
from adapters.harbor_matrix.gateway import (
    MODEL_ALIASES as ALIAS_TO_MODEL_FOR_TEST,
)
from adapters.harbor_matrix.gateway import (
    GatewayConfig,
    ProviderGateway,
)
from adapters.harbor_matrix.runner import (
    AGENT_TIMEOUT_MULTIPLIER,
    CODEX_VERSION,
    HARBOR_VERSION,
    HARTWELL_CODEX_IMPORT_PATH,
    HARTWELL_OPENCODE_IMPORT_PATH,
    MODEL_ALIASES,
    OPENCODE_VERSION,
    TASK_ORDER,
    BudgetExceededError,
    CompletedCommand,
    CreditBudget,
    CreditMeter,
    CreditMeterError,
    CreditSnapshot,
    HarborRunError,
    MatrixConfig,
    MatrixRunner,
    TrialFingerprint,
    build_harbor_command,
    classify_trial_result,
    full_batch_projection_from_launch,
    launch_projection,
    smoke_is_reusable,
    validate_batch_outcomes,
    validate_harbor_version,
)
from adapters.harness.openrouter_client import MODEL_PROVIDERS


@pytest.fixture
def gateway_config() -> GatewayConfig:
    return GatewayConfig(
        openrouter_api_key="openrouter-host-secret",
        gateway_token="ephemeral-container-secret",
        bind_host="127.0.0.1",
        port=0,
        upstream_url="https://openrouter.test/api/v1/responses",
    )


async def test_gateway_pins_chat_completions_for_opencode(
    gateway_config: GatewayConfig,
) -> None:
    """opencode's openai provider speaks Chat Completions, not Responses.

    The gateway pins and forwards either endpoint, routed by inbound path
    to the matching OpenRouter URL, so one gateway serves both harnesses.
    """

    seen: dict[str, object] = {}

    async def upstream(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads((await request.aread()).decode())
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"id": "chatcmpl-1", "choices": []},
        )

    gateway = ProviderGateway(
        gateway_config, upstream_transport=httpx.MockTransport(upstream)
    )
    async with gateway:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{gateway.local_url}/v1/chat/completions",
                headers={"Authorization": "Bearer ephemeral-container-secret"},
                json={
                    "model": "opus-5",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

    assert response.status_code == 200
    assert seen["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert seen["body"]["model"] == "anthropic/claude-opus-5"
    assert seen["body"]["provider"] == {
        "order": ["amazon-bedrock/us-east-1", "amazon-bedrock"],
        "allow_fallbacks": False,
    }


async def test_gateway_restores_alias_and_injects_provider_pin(
    gateway_config: GatewayConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seen: dict[str, object] = {}

    async def upstream(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads((await request.aread()).decode())
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "x-upstream": "kept"},
            json={"id": "response-1", "status": "completed"},
        )

    caplog.set_level(logging.INFO, logger="adapters.harbor_matrix.gateway")
    transport = httpx.MockTransport(upstream)
    gateway = ProviderGateway(gateway_config, upstream_transport=transport)
    async with gateway:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{gateway.local_url}/v1/responses",
                headers={"Authorization": "Bearer ephemeral-container-secret"},
                json={
                    "model": "gpt-5.6-sol",
                    "input": "private client request",
                    "stream": False,
                },
            )

    assert response.status_code == 200
    assert response.headers["x-upstream"] == "kept"
    assert response.json() == {"id": "response-1", "status": "completed"}
    assert seen["authorization"] == "Bearer openrouter-host-secret"
    assert seen["body"] == {
        "model": "openai/gpt-5.6-sol",
        "input": "private client request",
        "stream": False,
        # Azure and Bedrock are the first-party-grade endpoints this key's
        # guardrail permits; the direct openai/anthropic tags 404 for it.
        "provider": {"order": ["azure"], "allow_fallbacks": False},
    }
    assert gateway.provenance[0].model == "openai/gpt-5.6-sol"
    assert (
        gateway.provenance[0].enforced_provider_order
        == MODEL_PROVIDERS["openai/gpt-5.6-sol"]
    )
    assert gateway.provenance[0].actual_provider is None
    log_text = caplog.text
    assert "openai/gpt-5.6-sol" in log_text
    assert "private client request" not in log_text
    assert "openrouter-host-secret" not in log_text
    assert "ephemeral-container-secret" not in log_text
    assert "Authorization" not in log_text


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


async def test_gateway_passes_sse_bytes_and_errors_through(
    gateway_config: GatewayConfig,
) -> None:
    calls = 0

    async def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads((await request.aread()).decode())
        assert body["model"] == "anthropic/claude-opus-5"
        if calls == 1:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream", "x-stream": "yes"},
                stream=ChunkStream([b"data: one\n\n", b"data: [DONE]\n\n"]),
            )
        return httpx.Response(
            429,
            headers={"content-type": "application/json", "retry-after": "7"},
            content=b'{"error":{"message":"rate limited"}}',
        )

    gateway = ProviderGateway(
        gateway_config, upstream_transport=httpx.MockTransport(upstream)
    )
    headers = {"Authorization": "Bearer ephemeral-container-secret"}
    async with gateway:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{gateway.local_url}/v1/responses",
                headers=headers,
                json={"model": "opus-5", "stream": True},
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["x-stream"] == "yes"
                assert await response.aread() == b"data: one\n\ndata: [DONE]\n\n"
            error = await client.post(
                f"{gateway.local_url}/v1/responses",
                headers=headers,
                json={"model": "opus-5"},
            )

    assert error.status_code == 429
    assert error.headers["retry-after"] == "7"
    assert error.content == b'{"error":{"message":"rate limited"}}'
    assert [record.status for record in gateway.provenance] == [200, 429]


async def test_gateway_rejects_bad_auth_and_cleans_up_on_failure(
    gateway_config: GatewayConfig,
) -> None:
    upstream_calls = 0

    async def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal upstream_calls
        upstream_calls += 1
        return httpx.Response(200, json={})

    gateway = ProviderGateway(
        gateway_config, upstream_transport=httpx.MockTransport(upstream)
    )
    with pytest.raises(RuntimeError, match="intentional"):
        async with gateway:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{gateway.local_url}/v1/responses",
                    headers={"Authorization": "Bearer wrong"},
                    json={"model": "opus-5", "input": "secret"},
                )
                assert response.status_code == 401
                assert upstream_calls == 0
            raise RuntimeError("intentional")

    assert not gateway.running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.post(gateway.local_url, timeout=0.1)


async def test_gateway_generic_failure_log_never_contains_exception_or_request_secrets(
    gateway_config: GatewayConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        await request.aread()
        raise RuntimeError(
            "private client request openrouter-host-secret "
            "ephemeral-container-secret Authorization"
        )

    caplog.set_level(logging.ERROR, logger="adapters.harbor_matrix.gateway")
    gateway = ProviderGateway(
        gateway_config, upstream_transport=httpx.MockTransport(upstream)
    )
    async with gateway:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{gateway.local_url}/v1/responses",
                headers={"Authorization": "Bearer ephemeral-container-secret"},
                json={"model": "opus-5", "input": "private client request"},
            )

    assert response.status_code == 502
    assert "provider gateway transport failure" in caplog.text
    for secret in (
        "private client request",
        "openrouter-host-secret",
        "ephemeral-container-secret",
        "Authorization",
    ):
        assert secret not in caplog.text


def test_harbor_command_is_provider_aliased_and_version_pinned(tmp_path: Path) -> None:
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tmp_path / "tasks",
        jobs_dir=tmp_path / "jobs",
        run_id="final-matrix",
        attempts=3,
        concurrency=8,
        projected_worst_case_batch_usd=2.5,
    )
    command = build_harbor_command(
        config,
        "fee-dispute-reconstruction",
        gateway_port=43121,
        gateway_env_file=tmp_path / "gateway.env",
    )

    assert command[:3] == ("harbor", "run", "-p")
    assert command[command.index("-a") + 1] == (
        "adapters.harbor_matrix.codex_agent:HartwellCodex"
    )
    assert command.count("-m") == len(MODEL_ALIASES)
    for alias in MODEL_ALIASES:
        assert alias in command
    assert ("--ak", f"version={CODEX_VERSION}") == (
        command[command.index("--ak")],
        command[command.index("--ak") + 1],
    )
    assert "compaction_mode=custom-provider-local" in command
    assert "OPENAI_BASE_URL=http://host.docker.internal:43121/v1" in command
    assert command[command.index("--env-file") + 1] == str(tmp_path / "gateway.env")
    assert "ephemeral-only" not in " ".join(command)
    assert not any(argument.startswith("OPENAI_API_KEY=") for argument in command)
    assert "host.docker.internal" in command
    assert command[command.index("-n") + 1] == "8"
    assert command[command.index("--n-concurrent-agents") + 1] == "8"
    assert command[command.index("-k") + 1] == "3"
    assert command[command.index("--agent-timeout-multiplier") + 1] == "2.0"
    assert command[command.index("--job-name") + 1] == (
        "final-matrix-01-fee-dispute-reconstruction"
    )
    assert validate_harbor_version("harbor 0.18.0\n") == HARBOR_VERSION
    with pytest.raises(ValueError, match="0.18.0"):
        validate_harbor_version("harbor 0.19.0")


def test_harbor_command_selects_opencode_harness(tmp_path: Path) -> None:
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tmp_path / "tasks",
        jobs_dir=tmp_path / "jobs",
        run_id="opencode-matrix",
        harness="opencode",
        attempts=3,
        concurrency=8,
        projected_worst_case_batch_usd=2.5,
    )
    command = build_harbor_command(
        config,
        "fee-dispute-reconstruction",
        gateway_port=43121,
        gateway_env_file=tmp_path / "gateway.env",
    )

    # The opencode import path replaces the codex one.
    assert command[command.index("-a") + 1] == HARTWELL_OPENCODE_IMPORT_PATH
    # Both models run through opencode's gateway-backed openai provider, so the
    # alias is prefixed with ``openai/`` -- the segment the gateway restores.
    model_args = [command[i + 1] for i, value in enumerate(command) if value == "-m"]
    assert model_args == [f"openai/{alias}" for alias in MODEL_ALIASES]
    assert model_args == ["openai/opus-5", "openai/gpt-5.6-sol"]
    # The version pin survives (base __init__ param); the codex-only compaction
    # kwarg is dropped, leaving exactly one --ak pair.
    assert command.count("--ak") == 1
    assert ("--ak", f"version={OPENCODE_VERSION}") == (
        command[command.index("--ak")],
        command[command.index("--ak") + 1],
    )
    assert not any(argument.startswith("compaction_mode=") for argument in command)
    # Every other flag is identical to the codex path.
    assert "OPENAI_BASE_URL=http://host.docker.internal:43121/v1" in command
    assert command[command.index("--env-file") + 1] == str(tmp_path / "gateway.env")
    assert command[command.index("--allow-agent-host") + 1] == "host.docker.internal"
    assert command[command.index("--max-retries") + 1] == "0"
    assert command[command.index("--job-name") + 1] == (
        "opencode-matrix-01-fee-dispute-reconstruction"
    )


def test_harbor_command_defaults_to_codex_and_leaves_it_unchanged(
    tmp_path: Path,
) -> None:
    base = dict(
        repository=tmp_path,
        tasks_root=tmp_path / "tasks",
        jobs_dir=tmp_path / "jobs",
        run_id="default-matrix",
        attempts=3,
        concurrency=8,
        projected_worst_case_batch_usd=2.5,
    )
    defaulted = MatrixConfig(**base)
    explicit = MatrixConfig(harness="codex", **base)
    assert defaulted.harness == "codex"

    kwargs = dict(gateway_port=43121, gateway_env_file=tmp_path / "gateway.env")
    default_command = build_harbor_command(
        defaulted, "fee-dispute-reconstruction", **kwargs
    )
    explicit_command = build_harbor_command(
        explicit, "fee-dispute-reconstruction", **kwargs
    )
    opencode_command = build_harbor_command(
        MatrixConfig(harness="opencode", **base),
        "fee-dispute-reconstruction",
        **kwargs,
    )

    # Omitting --harness is byte-for-byte identical to selecting codex, and both
    # keep the codex markers the opencode path drops or rewrites.
    assert default_command == explicit_command
    assert (
        default_command[default_command.index("-a") + 1] == HARTWELL_CODEX_IMPORT_PATH
    )
    model_args = [
        default_command[i + 1]
        for i, value in enumerate(default_command)
        if value == "-m"
    ]
    assert model_args == list(MODEL_ALIASES)
    assert not any(argument.startswith("openai/") for argument in default_command)
    assert "compaction_mode=custom-provider-local" in default_command
    assert default_command != opencode_command


def test_hartwell_opencode_routes_openai_key_through_gateway_token(
    tmp_path: Path,
) -> None:
    """opencode's openai provider reads OPENAI_API_KEY; feed it the gateway token.

    Runs under Harbor's own interpreter via the launcher shebang because the
    ``harbor`` package is not importable from the adapter's test env, mirroring
    ``test_hartwell_codex_uses_local_compaction``.
    """

    harbor = shutil.which("harbor")
    if harbor is None:
        pytest.skip("Harbor is not installed")
    shebang = Path(harbor).resolve().read_text(encoding="utf-8").splitlines()[0]
    if not shebang.startswith("#!"):
        pytest.skip("Harbor launcher has no Python shebang")
    adapter_root = Path(matrix_runner.__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(adapter_root), environment.get("PYTHONPATH")))
    )
    script = "\n".join(
        (
            "from pathlib import Path",
            "from adapters.harbor_matrix.opencode_agent import (",
            "    HartwellOpencode,",
            ")",
            "agent = HartwellOpencode(",
            f"    logs_dir=Path({str(tmp_path)!r}),",
            "    model_name='openai/opus-5',",
            f"    version={OPENCODE_VERSION!r},",
            "    extra_env={",
            "        'OPENAI_BASE_URL': 'http://host.docker.internal:43121/v1',",
            "        'HARTWELL_GATEWAY_TOKEN': 'ephemeral-test',",
            "    },",
            ")",
            "print(agent._get_env('OPENAI_API_KEY') == 'ephemeral-test')",
            "print(agent._get_env('OPENAI_BASE_URL'))",
        )
    )
    completed = subprocess.run(
        [shebang[2:], "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    # The gateway token is surfaced as OPENAI_API_KEY; the base URL is untouched.
    assert lines[0] == "True"
    assert lines[-1] == "http://host.docker.internal:43121/v1"


def test_hartwell_codex_uses_local_compaction(tmp_path: Path) -> None:
    harbor = shutil.which("harbor")
    if harbor is None:
        pytest.skip("Harbor is not installed")
    shebang = Path(harbor).resolve().read_text(encoding="utf-8").splitlines()[0]
    if not shebang.startswith("#!"):
        pytest.skip("Harbor launcher has no Python shebang")
    adapter_root = Path(matrix_runner.__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(adapter_root), environment.get("PYTHONPATH")))
    )
    script = "\n".join(
        (
            "from pathlib import Path",
            "from adapters.harbor_matrix.codex_agent import HartwellCodex",
            "agent = HartwellCodex(",
            f"    logs_dir=Path({str(tmp_path)!r}),",
            "    model_name='gpt-5.6-sol',",
            f"    version={CODEX_VERSION!r},",
            "    compaction_mode='custom-provider-local',",
            "    extra_env={",
            "        'OPENAI_BASE_URL': 'http://host.docker.internal:43121/v1',",
            "        'HARTWELL_GATEWAY_TOKEN': 'ephemeral-test',",
            "    },",
            ")",
            "print(agent.build_cli_flags())",
            "print(agent._get_env('OPENAI_API_KEY') == 'ephemeral-test')",
        )
    )
    completed = subprocess.run(
        [shebang[2:], "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--disable remote_compaction_v2" in completed.stdout
    assert "model_provider=hartwell_gateway" in completed.stdout
    assert "model_providers.hartwell_gateway.base_url" in completed.stdout
    assert "http://host.docker.internal:43121/v1" in completed.stdout
    assert "model_providers.hartwell_gateway.env_key=OPENAI_API_KEY" in completed.stdout
    assert "model_providers.hartwell_gateway.wire_api=responses" in completed.stdout
    assert (
        "model_providers.hartwell_gateway.supports_websockets=false" in completed.stdout
    )
    assert completed.stdout.splitlines()[-1] == "True"


def test_hartwell_codex_strips_unified_exec_for_sol_only(tmp_path: Path) -> None:
    """Sol's exec payload aborts Codex's unified_exec router; drop it for Sol.

    Every Sol cell failed with "tool exec invoked with incompatible payload"
    before touching a tool. Removing --enable unified_exec falls Codex back
    to its standard shell tool. Opus was measured WITH unified_exec and must
    keep it, or its scores would not survive the harness change.
    """

    harbor = shutil.which("harbor")
    if harbor is None:
        pytest.skip("Harbor is not installed")
    shebang = Path(harbor).resolve().read_text(encoding="utf-8").splitlines()[0]
    if not shebang.startswith("#!"):
        pytest.skip("Harbor launcher has no Python shebang")
    adapter_root = Path(matrix_runner.__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(adapter_root), environment.get("PYTHONPATH")))
    )
    command = (
        "codex exec --dangerously-bypass-approvals-and-sandbox "
        "--skip-git-repo-check --model M --json --enable unified_exec -- task"
    )
    script = "\n".join(
        (
            "from pathlib import Path",
            "from adapters.harbor_matrix.codex_agent import HartwellCodex",
            f"cmd = {command!r}",
            "for model in ('gpt-5.6-sol', 'anthropic/claude-opus-5'):",
            "    agent = HartwellCodex(",
            f"        logs_dir=Path({str(tmp_path)!r}), model_name=model,",
            f"        version={CODEX_VERSION!r},",
            "        compaction_mode='custom-provider-local',",
            "    )",
            "    keep = agent._uses_unified_exec()",
            "    print(f'{model} keeps_unified_exec={keep}')",
            # A setup step that also mentions codex must be left alone.
            "agent = HartwellCodex(",
            f"    logs_dir=Path({str(tmp_path)!r}), model_name='gpt-5.6-sol',",
            f"    version={CODEX_VERSION!r}, compaction_mode='custom-provider-local')",
            "print('setup_untouched=' + str(",
            "    'unified_exec' in 'cat >config.toml # codex config'))",
        )
    )
    completed = subprocess.run(
        [shebang[2:], "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert "gpt-5.6-sol keeps_unified_exec=False" in completed.stdout
    assert "anthropic/claude-opus-5 keeps_unified_exec=True" in completed.stdout


async def test_subprocess_runner_exposes_custom_agent_import_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class Process:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def create_subprocess_exec(*command: str, **kwargs: object) -> Process:
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return Process()

    monkeypatch.setattr(
        matrix_runner.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )
    await matrix_runner.SubprocessCommandRunner().run(
        ("harbor", "--version"), cwd=tmp_path
    )

    environment = captured["env"]
    assert isinstance(environment, dict)
    adapter_root = Path(matrix_runner.__file__).resolve().parents[2]
    assert str(adapter_root) in environment["PYTHONPATH"].split(os.pathsep)


def test_task_order_is_fixed() -> None:
    assert TASK_ORDER == (
        "fee-dispute-reconstruction",
        "client-departure-postmortem",
        "billing-hygiene-audit",
        "second-read-audit",
        "visitor-log-audit",
        "operative-deadline",
        "standard-drift",
        "vanished-clause",
        "settlement-authority-audit",
    )


def test_matrix_cli_requires_explicit_run_and_cost_projection(tmp_path: Path) -> None:
    config = parse_args(
        [
            "--run-id",
            "matrix-2026-08-10",
            "--projected-worst-case-batch-usd",
            "3.25",
            "--repository",
            str(tmp_path),
        ]
    )
    assert config.run_id == "matrix-2026-08-10"
    assert config.tasks_root == tmp_path / "datasets/hartwell/tasks"
    assert config.jobs_dir == tmp_path / "jobs"
    assert config.attempts == 3
    assert config.concurrency == 8
    assert config.budget_baseline_usage == pytest.approx(32.2139)
    assert config.project_cap_usd == pytest.approx(25.0)
    with pytest.raises(ValidationError):
        MatrixConfig(
            repository=tmp_path,
            tasks_root=tmp_path / "tasks",
            jobs_dir=tmp_path / "jobs",
            run_id="not-three",
            attempts=2,
            projected_worst_case_batch_usd=1,
        )


def test_matrix_cli_records_an_incremental_budget_checkpoint(tmp_path: Path) -> None:
    config = parse_args(
        [
            "--run-id",
            "continued-matrix",
            "--projected-worst-case-batch-usd",
            "3.25",
            "--budget-baseline-usage",
            "56.005689513",
            "--project-cap-usd",
            "12.50",
            "--repository",
            str(tmp_path),
        ]
    )

    assert config.budget_baseline_usage == pytest.approx(56.005689513)
    assert config.project_cap_usd == pytest.approx(12.5)

    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=FakeCommands(),
        credit_meter=FakeCreditMeter(),
    )
    assert runner._budget.baseline_usage == pytest.approx(56.005689513)
    assert runner._budget.project_cap_usd == pytest.approx(12.5)
    assert runner._budget.cap_usage == pytest.approx(68.505689513)


def test_matrix_cli_can_select_canonical_task_batches(tmp_path: Path) -> None:
    config = parse_args(
        [
            "--run-id",
            "targeted-matrix",
            "--projected-worst-case-batch-usd",
            "3.25",
            "--task",
            "vanished-clause",
            "--task",
            "billing-hygiene-audit",
            "--repository",
            str(tmp_path),
        ]
    )

    assert config.tasks == (
        "billing-hygiene-audit",
        "vanished-clause",
    )

    with pytest.raises(ValidationError, match="tasks"):
        MatrixConfig(
            repository=tmp_path,
            tasks_root=tmp_path / "tasks",
            jobs_dir=tmp_path / "jobs",
            run_id="duplicate-task",
            projected_worst_case_batch_usd=1,
            tasks=("vanished-clause", "vanished-clause"),
        )


def test_diagnostic_smoke_cli_requires_exactly_one_task(tmp_path: Path) -> None:
    config = parse_args(
        [
            "--run-id",
            "billing-screen",
            "--projected-worst-case-batch-usd",
            "9.0",
            "--task",
            "billing-hygiene-audit",
            "--diagnostic-smoke",
            "--repository",
            str(tmp_path),
        ]
    )

    assert config.diagnostic_smoke is True
    assert config.tasks == ("billing-hygiene-audit",)
    assert config.diagnostic_models == MODEL_ALIASES

    single_model = parse_args(
        [
            "--run-id",
            "billing-luna-screen",
            "--projected-worst-case-batch-usd",
            "9.0",
            "--task",
            "billing-hygiene-audit",
            "--diagnostic-smoke",
            "--diagnostic-model",
            MODEL_ALIASES[0],
            "--repository",
            str(tmp_path),
        ]
    )
    assert single_model.diagnostic_models == (MODEL_ALIASES[0],)

    with pytest.raises(ValidationError, match="diagnostic_smoke"):
        MatrixConfig(
            repository=tmp_path,
            tasks_root=tmp_path / "tasks",
            jobs_dir=tmp_path / "jobs",
            run_id="multi-screen",
            tasks=("billing-hygiene-audit", "visitor-log-audit"),
            diagnostic_smoke=True,
            projected_worst_case_batch_usd=9.0,
        )

    with pytest.raises(ValidationError, match="diagnostic_models"):
        MatrixConfig(
            repository=tmp_path,
            tasks_root=tmp_path / "tasks",
            jobs_dir=tmp_path / "jobs",
            run_id="not-a-screen",
            diagnostic_models=(MODEL_ALIASES[0],),
            projected_worst_case_batch_usd=9.0,
        )


def _result(
    path: Path,
    *,
    exception_info: object = None,
    rewards: object = None,
) -> None:
    verifier = None if rewards is None else {"rewards": rewards}
    path.write_text(
        json.dumps({"exception_info": exception_info, "verifier_result": verifier}),
        encoding="utf-8",
    )


def test_trial_result_requires_complete_finite_verifier_metrics(tmp_path: Path) -> None:
    valid_zero = tmp_path / "valid-zero.json"
    _result(valid_zero, rewards={"reward": 0, "answer": 0, "process": 0.3})
    outcome = classify_trial_result(valid_zero)
    assert outcome.valid
    assert outcome.answer == 0.0

    exception = tmp_path / "exception.json"
    _result(
        exception,
        exception_info={"type": "AgentTimeoutError"},
        rewards={"reward": 0, "answer": 0, "process": 0},
    )
    assert not classify_trial_result(exception).valid
    assert classify_trial_result(exception).reason == "AgentTimeoutError"

    for name, rewards in {
        "missing": {"reward": 0, "answer": 0},
        "not-finite": {"reward": 0, "answer": float("nan"), "process": 0},
        "negative": {"reward": 0, "answer": 0, "process": -0.01},
        "above-one": {"reward": 0, "answer": 0, "process": 1.01},
        "reward-not-answer": {"reward": 0.4, "answer": 0.5, "process": 0},
        "malformed": None,
    }.items():
        result = tmp_path / f"{name}.json"
        if name == "malformed":
            result.write_text("not json", encoding="utf-8")
        else:
            _result(result, rewards=rewards)
        assert not classify_trial_result(result).valid


def test_batch_requires_each_model_attempt_cell(tmp_path: Path) -> None:
    outcomes = []
    for alias in MODEL_ALIASES:
        for attempt in range(3):
            path = tmp_path / f"{alias}-{attempt}.json"
            _result(path, rewards={"reward": 0, "answer": 0, "process": 0})
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["config"] = {"agent": {"model_name": alias}}
            raw["agent_info"] = {"version": CODEX_VERSION}
            path.write_text(json.dumps(raw), encoding="utf-8")
            outcomes.append(classify_trial_result(path))
    validate_batch_outcomes(tuple(outcomes), attempts=3)

    duplicate = outcomes[-1].model_copy(update={"model_alias": MODEL_ALIASES[0]})
    with pytest.raises(HarborRunError, match="model-attempt cells"):
        validate_batch_outcomes(tuple(outcomes[:-1] + [duplicate]), attempts=3)

    wrong_version = outcomes[-1].model_copy(update={"agent_version": "0.999.0"})
    with pytest.raises(HarborRunError, match="Codex"):
        validate_batch_outcomes(tuple(outcomes[:-1] + [wrong_version]), attempts=3)

    validate_batch_outcomes(
        tuple(outcomes[:3]), attempts=3, model_aliases=(MODEL_ALIASES[0],)
    )


def test_budget_enforces_project_cap_and_reserve() -> None:
    budget = CreditBudget()
    credits = CreditSnapshot(total_credits=100, total_usage=50.0)
    budget.assert_can_launch(credits, projected_worst_case_usd=5.7)
    with pytest.raises(BudgetExceededError):
        budget.assert_can_launch(credits, projected_worst_case_usd=5.714)
    assert budget.cap_usage == pytest.approx(57.2139)
    with pytest.raises(CreditMeterError, match="decreased"):
        budget.metered_cost(
            CreditSnapshot(total_credits=100, total_usage=50.0),
            CreditSnapshot(total_credits=100, total_usage=49.9),
        )
    with pytest.raises(BudgetExceededError, match="observed"):
        budget.assert_observed_within_cap(
            CreditSnapshot(total_credits=100, total_usage=57.3)
        )


def test_cost_projection_scales_with_launch_size() -> None:
    assert launch_projection(9.0, attempts_per_model=1) == pytest.approx(3.0)
    assert launch_projection(9.0, attempts_per_model=2) == pytest.approx(6.0)
    assert launch_projection(9.0, attempts_per_model=3) == pytest.approx(9.0)
    assert full_batch_projection_from_launch(
        2.5, attempts_per_model=1
    ) == pytest.approx(7.5)
    assert full_batch_projection_from_launch(
        5.0, attempts_per_model=2
    ) == pytest.approx(7.5)
    # Derived from the table rather than written out, so retargeting the
    # sign-off models cannot silently misprice a launch.
    full_batch_cells = 3 * len(MODEL_ALIASES)
    assert launch_projection(9.0, attempts_per_model=1, model_count=1) == pytest.approx(
        9.0 / full_batch_cells
    )
    assert full_batch_projection_from_launch(
        1.0, attempts_per_model=1, model_count=1
    ) == pytest.approx(float(full_batch_cells))
    with pytest.raises(ValueError, match="attempts"):
        launch_projection(1.0, attempts_per_model=0)
    with pytest.raises(ValueError, match="model_count"):
        launch_projection(1.0, attempts_per_model=1, model_count=0)


async def test_credit_meter_uses_authoritative_endpoint_without_leaking_key() -> None:
    seen_authorization = ""

    async def credits(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers["authorization"]
        # Per-key, so a pooled org's other traffic is not billed to this run.
        assert str(request.url) == "https://openrouter.ai/api/v1/key"
        return httpx.Response(200, json={"data": {"usage": 40.433}})

    meter = CreditMeter("meter-host-secret", transport=httpx.MockTransport(credits))
    try:
        snapshot = await meter.query()
    finally:
        await meter.aclose()

    assert snapshot.total_usage == pytest.approx(40.433)
    assert seen_authorization == "Bearer meter-host-secret"


class FakeCreditMeter:
    def __init__(self, usages: list[float] | None = None) -> None:
        self.queries = 0
        self._usages = usages

    async def query(self) -> CreditSnapshot:
        usage = (
            self._usages[self.queries]
            if self._usages is not None
            else 40.0 + (self.queries * 0.25)
        )
        snapshot = CreditSnapshot(
            total_credits=100,
            total_usage=usage,
        )
        self.queries += 1
        return snapshot


class FakeCommands:
    def __init__(
        self,
        *,
        invalid_smoke: bool = False,
        mutate_environment_after_smoke: Path | None = None,
        send_gateway_requests: bool = False,
        write_results: bool = True,
    ) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.harbor_runs: list[tuple[str, int, tuple[str, ...], str]] = []
        self.invalid_smoke = invalid_smoke
        self.mutate_environment_after_smoke = mutate_environment_after_smoke
        self.send_gateway_requests = send_gateway_requests
        self.write_results = write_results
        self.gateway_env_files: list[Path] = []

    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        self.commands.append(command)
        if command == ("harbor", "--version"):
            return CompletedCommand(returncode=0, stdout="harbor 0.18.0\n")
        if command == ("git", "rev-parse", "HEAD"):
            return CompletedCommand(returncode=0, stdout="deadbeef\n")
        if command[:3] == ("docker", "image", "inspect"):
            return CompletedCommand(returncode=0, stdout="sha256:image\n")
        task_name = Path(command[command.index("-p") + 1]).name
        jobs_dir = Path(command[command.index("-o") + 1])
        job_name = command[command.index("--job-name") + 1]
        attempts = int(command[command.index("-k") + 1])
        aliases = [
            command[index + 1] for index, value in enumerate(command) if value == "-m"
        ]
        gateway_env_file = Path(command[command.index("--env-file") + 1])
        self.gateway_env_files.append(gateway_env_file)
        assert gateway_env_file.stat().st_mode & 0o777 == 0o600
        self.harbor_runs.append((task_name, attempts, tuple(aliases), job_name))
        if self.send_gateway_requests:
            base_url_arg = next(
                argument
                for argument in command
                if argument.startswith("OPENAI_BASE_URL=")
            )
            token_line = gateway_env_file.read_text(encoding="utf-8").strip()
            token_key, separator, token = token_line.partition("=")
            assert token_key == "HARTWELL_GATEWAY_TOKEN"
            assert separator == "="
            port = base_url_arg.split(":")[-1].split("/")[0]
            async with httpx.AsyncClient() as client:
                for alias in aliases:
                    await client.post(
                        f"http://127.0.0.1:{port}/v1/responses",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"model": alias, "input": "redacted"},
                    )
        if self.write_results:
            for alias in aliases:
                for attempt in range(attempts):
                    trial = jobs_dir / job_name / f"{alias}-{attempt}"
                    trial.mkdir(parents=True)
                    (trial / "result.json").write_text(
                        json.dumps(
                            {
                                "trial_name": trial.name,
                                "config": {"agent": {"model_name": alias}},
                                "agent_info": {"version": CODEX_VERSION},
                                "exception_info": None,
                                "verifier_result": {
                                    "rewards": {
                                        "reward": (
                                            0.3
                                            if self.invalid_smoke
                                            and "smoke" in job_name
                                            else 0.2
                                        ),
                                        "answer": 0.2,
                                        "process": 0.8,
                                    }
                                },
                            }
                        ),
                        encoding="utf-8",
                    )
        if "smoke" in job_name and self.mutate_environment_after_smoke is not None:
            self.mutate_environment_after_smoke.write_bytes(b"rematerialized")
        return CompletedCommand(returncode=0)


class BlockingHarborCommands(FakeCommands):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False

    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        if (
            command == ("harbor", "--version")
            or command[:3]
            == (
                "docker",
                "image",
                "inspect",
            )
            or command == ("git", "rev-parse", "HEAD")
        ):
            return await super().run(command, cwd=cwd)
        self.commands.append(command)
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class PartialResultBlockingHarborCommands(BlockingHarborCommands):
    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        if (
            command == ("harbor", "--version")
            or command[:3] == ("docker", "image", "inspect")
            or command == ("git", "rev-parse", "HEAD")
        ):
            return await FakeCommands.run(self, command, cwd=cwd)
        self.commands.append(command)
        jobs_dir = Path(command[command.index("-o") + 1])
        job_name = command[command.index("--job-name") + 1]
        trial = jobs_dir / job_name / "opus-5-0"
        trial.mkdir(parents=True)
        (trial / "result.json").write_text(
            json.dumps(
                {
                    "trial_name": trial.name,
                    "config": {"agent": {"model_name": "opus-5"}},
                    "agent_info": {"version": CODEX_VERSION},
                    "exception_info": None,
                    "verifier_result": {
                        "rewards": {"reward": 0.27, "answer": 0.27, "process": 1.0}
                    },
                }
            ),
            encoding="utf-8",
        )
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class RecordingJobCleaner:
    def __init__(self) -> None:
        self.jobs: list[Path] = []

    async def cleanup(self, job_dir: Path) -> None:
        self.jobs.append(job_dir)


async def test_matrix_runner_executes_one_task_batch_at_a_time_in_order(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    for task_name in TASK_ORDER:
        task = tasks_root / task_name
        task.mkdir(parents=True)
        (task / "task.toml").write_text('version = "1.3"\n', encoding="utf-8")
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id="offline-matrix",
        projected_worst_case_batch_usd=1.0,
    )
    commands = FakeCommands(send_gateway_requests=True)
    meter = FakeCreditMeter()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=meter,
        gateway_transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "completed"})
        ),
    )

    report = await runner.run()

    assert [run[:3] for run in commands.harbor_runs] == [
        ("fee-dispute-reconstruction", 1, MODEL_ALIASES),
        ("fee-dispute-reconstruction", 2, MODEL_ALIASES),
        *[(task_name, 3, MODEL_ALIASES) for task_name in TASK_ORDER[1:]],
    ]
    assert "smoke" in commands.harbor_runs[0][3]
    assert "additional" in commands.harbor_runs[1][3]
    assert meter.queries == 1 + len(commands.harbor_runs)
    assert report.smoke is not None
    assert report.smoke.valid
    assert len(report.smoke.trials) == len(MODEL_ALIASES)
    assert [batch.task_name for batch in report.batches] == list(TASK_ORDER)
    assert all(len(batch.trials) == 3 * len(MODEL_ALIASES) for batch in report.batches)
    assert all(
        trial.outcome.valid for batch in report.batches for trial in batch.trials
    )
    # One launch per task, plus the extra fee-dispute smoke that precedes them.
    launch_count = len(TASK_ORDER) + 1
    assert [launch.sequence for launch in report.launches] == list(
        range(1, launch_count + 1)
    )
    assert [launch.phase for launch in report.launches[:2]] == [
        "smoke",
        "additional",
    ]
    assert [launch.task_name for launch in report.launches] == [
        "fee-dispute-reconstruction",
        *TASK_ORDER,
    ]
    assert all(
        launch.enforced_model_routes
        == {
            alias: MODEL_PROVIDERS[full_model]
            for alias, full_model in ALIAS_TO_MODEL_FOR_TEST.items()
        }
        for launch in report.launches
    )
    assert [
        (
            launch.gateway_sequences.start_exclusive,
            launch.gateway_sequences.end_inclusive,
        )
        for launch in report.launches
    ] == [
        (index * len(MODEL_ALIASES), (index + 1) * len(MODEL_ALIASES))
        for index in range(launch_count)
    ]
    assert all(record.actual_provider is None for record in report.gateway_provenance)
    assert all(
        trial.fingerprint.model == ALIAS_TO_MODEL_FOR_TEST[trial.outcome.model_alias]
        for batch in report.batches
        for trial in batch.trials
    )
    assert all(
        len([trial for trial in batch.trials if trial.outcome.model_alias == alias])
        == 3
        for batch in report.batches
        for alias in MODEL_ALIASES
    )
    persisted = json.loads(
        (config.jobs_dir / "offline-matrix-matrix.json").read_text(encoding="utf-8")
    )
    assert len(persisted["batches"]) == len(TASK_ORDER)
    assert persisted["smoke"]["valid"] is True
    assert persisted["failure"] is None
    assert commands.gateway_env_files
    assert all(not path.exists() for path in commands.gateway_env_files)


async def test_matrix_runner_executes_a_selected_non_fee_task_without_fee_smoke(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id="targeted-matrix",
        tasks=("billing-hygiene-audit",),
        projected_worst_case_batch_usd=1.0,
    )
    commands = FakeCommands()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=FakeCreditMeter(),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    report = await runner.run()

    assert commands.harbor_runs == [
        (
            "billing-hygiene-audit",
            3,
            MODEL_ALIASES,
            "targeted-matrix-03-billing-hygiene-audit",
        )
    ]
    assert report.smoke is None
    assert [batch.task_name for batch in report.batches] == ["billing-hygiene-audit"]
    assert report.batches[0].valid
    assert len(report.batches[0].trials) == 3 * len(MODEL_ALIASES)
    assert len(report.launches) == 1
    assert report.launches[0].phase == "matrix"


async def test_matrix_runner_executes_one_attempt_per_model_diagnostic_smoke(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id="billing-screen",
        tasks=("billing-hygiene-audit",),
        diagnostic_smoke=True,
        projected_worst_case_batch_usd=9.0,
    )
    commands = FakeCommands()
    meter = FakeCreditMeter()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=meter,
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    report = await runner.run()

    assert commands.harbor_runs == [
        (
            "billing-hygiene-audit",
            1,
            MODEL_ALIASES,
            "billing-screen-diagnostic-smoke-03-billing-hygiene-audit",
        )
    ]
    assert meter.queries == 2
    assert report.smoke is not None
    assert report.smoke.task_name == "billing-hygiene-audit"
    assert report.smoke.valid
    assert len(report.smoke.trials) == len(MODEL_ALIASES)
    assert report.batches == ()
    assert len(report.launches) == 1
    assert report.launches[0].phase == "diagnostic-smoke"
    assert report.launches[0].projected_worst_case_usd == pytest.approx(3.0)


async def test_matrix_runner_executes_a_single_model_diagnostic_smoke(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id="visitor-luna-screen",
        tasks=("visitor-log-audit",),
        diagnostic_smoke=True,
        diagnostic_models=(MODEL_ALIASES[0],),
        projected_worst_case_batch_usd=9.0,
    )
    commands = FakeCommands()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=FakeCreditMeter(),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    report = await runner.run()

    assert commands.harbor_runs == [
        (
            "visitor-log-audit",
            1,
            (MODEL_ALIASES[0],),
            "visitor-luna-screen-diagnostic-smoke-05-visitor-log-audit",
        )
    ]
    assert report.smoke is not None
    assert report.smoke.valid
    assert len(report.smoke.trials) == 1
    assert report.launches[0].enforced_model_routes == {
        MODEL_ALIASES[0]: MODEL_PROVIDERS[ALIAS_TO_MODEL_FOR_TEST[MODEL_ALIASES[0]]]
    }
    # One model, one attempt, out of a 3-attempt full batch across the
    # sign-off set; derived so retargeting the models cannot misprice it.
    assert report.launches[0].projected_worst_case_usd == pytest.approx(
        9.0 / (3 * len(MODEL_ALIASES))
    )


async def test_invalid_smoke_is_persisted_and_stops_before_final_fee_attempts(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = _matrix_config(tmp_path, tasks_root, run_id="invalid-smoke")
    commands = FakeCommands(invalid_smoke=True)
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=FakeCreditMeter(),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(HarborRunError, match="smoke"):
        await runner.run()

    assert len(commands.harbor_runs) == 1
    persisted = json.loads(
        (config.jobs_dir / "invalid-smoke-matrix.json").read_text(encoding="utf-8")
    )
    assert persisted["smoke"]["valid"] is False
    assert persisted["smoke"]["failure"]
    assert persisted["failure"]
    assert persisted["batches"] == []
    assert commands.gateway_env_files
    assert all(not path.exists() for path in commands.gateway_env_files)


async def test_existing_smoke_job_is_rejected_before_harbor_or_post_metering(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = _matrix_config(tmp_path, tasks_root, run_id="stale-job")
    stale_job = config.jobs_dir / "stale-job-smoke-01-fee-dispute-reconstruction"
    for alias in MODEL_ALIASES:
        trial = stale_job / f"old-{alias}"
        trial.mkdir(parents=True)
        (trial / "result.json").write_text(
            json.dumps(
                {
                    "trial_name": trial.name,
                    "config": {"agent": {"model_name": alias}},
                    "agent_info": {"version": CODEX_VERSION},
                    "exception_info": None,
                    "verifier_result": {
                        "rewards": {"reward": 1, "answer": 1, "process": 1}
                    },
                }
            ),
            encoding="utf-8",
        )
    commands = FakeCommands(write_results=False)
    meter = FakeCreditMeter()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=meter,
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(HarborRunError, match="already exists"):
        await runner.run()

    assert commands.harbor_runs == []
    assert meter.queries == 1
    persisted = json.loads(
        (config.jobs_dir / "stale-job-matrix.json").read_text(encoding="utf-8")
    )
    assert persisted["smoke"] is None
    assert persisted["batches"] == []
    assert persisted["launches"] == []
    assert "old-opus-5" not in json.dumps(persisted)


async def test_existing_matrix_report_refuses_run_without_overwriting(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = _matrix_config(tmp_path, tasks_root, run_id="existing-report")
    report_path = config.jobs_dir / "existing-report-matrix.json"
    report_path.parent.mkdir(parents=True)
    original = b'{"do_not_overwrite":true}\n'
    report_path.write_bytes(original)
    commands = FakeCommands()
    meter = FakeCreditMeter()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=meter,
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(HarborRunError, match="matrix report already exists"):
        await runner.run()

    assert commands.commands == []
    assert meter.queries == 0
    assert report_path.read_bytes() == original


async def test_rematerialized_environment_invalidates_smoke_before_reuse(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    state = tasks_root / "fee-dispute-reconstruction/environment/.workbench/state.db"
    state.parent.mkdir(parents=True)
    state.write_bytes(b"original")
    config = _matrix_config(tmp_path, tasks_root, run_id="changed-environment")
    commands = FakeCommands(mutate_environment_after_smoke=state)
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=FakeCreditMeter(),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(HarborRunError, match="fingerprint"):
        await runner.run()

    assert len(commands.harbor_runs) == 1
    persisted = json.loads(
        (config.jobs_dir / "changed-environment-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["smoke"]["valid"] is False
    assert "fingerprint" in persisted["smoke"]["failure"]


async def test_post_batch_cap_breach_is_persisted_before_runner_stops(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = _matrix_config(tmp_path, tasks_root, run_id="cap-breach")
    commands = FakeCommands()
    meter = FakeCreditMeter([53.0, 53.1, 57.3])
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=meter,
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(BudgetExceededError, match="observed"):
        await runner.run()

    assert len(commands.harbor_runs) == 2
    persisted = json.loads(
        (config.jobs_dir / "cap-breach-matrix.json").read_text(encoding="utf-8")
    )
    assert persisted["smoke"]["valid"] is True
    assert len(persisted["batches"]) == 1
    assert persisted["batches"][0]["task_name"] == "fee-dispute-reconstruction"
    assert "observed" in persisted["failure"]


async def test_in_flight_meter_cancels_a_batch_that_exceeds_its_authorization(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = _matrix_config(tmp_path, tasks_root, run_id="in-flight-cap").model_copy(
        update={"credit_poll_interval_sec": 0.01}
    )
    commands = BlockingHarborCommands()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        credit_meter=FakeCreditMeter([50.0, 51.1, 51.1]),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(BudgetExceededError, match="in-flight.*authorized"):
        await runner.run()

    assert commands.cancelled
    persisted = json.loads(
        (config.jobs_dir / "in-flight-cap-matrix.json").read_text(encoding="utf-8")
    )
    assert "in-flight" in persisted["failure"]
    assert persisted["batches"] == []
    assert len(persisted["launches"]) == 1
    assert persisted["launches"][0]["valid"] is False
    assert persisted["launches"][0]["metered_cost_usd"] == pytest.approx(1.1)


async def test_in_flight_stop_preserves_completed_diagnostic_evidence(
    tmp_path: Path,
) -> None:
    tasks_root = _make_tasks(tmp_path)
    config = MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id="partial-diagnostic",
        tasks=("visitor-log-audit",),
        diagnostic_smoke=True,
        projected_worst_case_batch_usd=1.0,
        credit_poll_interval_sec=0.01,
    )
    commands = PartialResultBlockingHarborCommands()
    cleaner = RecordingJobCleaner()
    runner = MatrixRunner(
        config,
        openrouter_api_key="host-only",
        gateway_token="ephemeral-only",
        commands=commands,
        job_cleaner=cleaner,
        credit_meter=FakeCreditMeter([50.0, 51.1, 51.1]),
        gateway_transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(BudgetExceededError, match="in-flight.*authorized"):
        await runner.run()

    persisted = json.loads(
        (config.jobs_dir / "partial-diagnostic-matrix.json").read_text(encoding="utf-8")
    )
    assert persisted["smoke"]["valid"] is False
    assert len(persisted["smoke"]["trials"]) == 1
    assert persisted["smoke"]["trials"][0]["outcome"]["valid"] is True
    assert persisted["smoke"]["trials"][0]["outcome"]["answer"] == 0.27
    assert cleaner.jobs == [
        config.jobs_dir / "partial-diagnostic-diagnostic-smoke-05-visitor-log-audit"
    ]


def test_cancelled_job_cleanup_targets_only_exact_trial_compose_projects(
    tmp_path: Path,
) -> None:
    job = tmp_path / "job"
    (job / "visitor-log-audit__AbC123").mkdir(parents=True)
    (job / "visitor-log-audit__z9Y8x7").mkdir()
    (job / "result.json").write_text("{}", encoding="utf-8")
    (job / "untrusted name").mkdir()

    assert matrix_runner._compose_projects_for_job(job) == (
        "visitor-log-audit__abc123__env",
        "visitor-log-audit__z9y8x7__env",
    )


def _make_tasks(tmp_path: Path) -> Path:
    tasks_root = tmp_path / "tasks"
    for task_name in TASK_ORDER:
        task = tasks_root / task_name
        task.mkdir(parents=True)
        (task / "task.toml").write_text('version = "1.3"\n', encoding="utf-8")
    return tasks_root


def _matrix_config(tmp_path: Path, tasks_root: Path, *, run_id: str) -> MatrixConfig:
    return MatrixConfig(
        repository=tmp_path,
        tasks_root=tasks_root,
        jobs_dir=tmp_path / "jobs",
        run_id=run_id,
        projected_worst_case_batch_usd=1.0,
    )


def test_fingerprint_is_content_sensitive_and_smoke_requires_exact_match(
    tmp_path: Path,
) -> None:
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "task.toml").write_text("version = '1.0'\n", encoding="utf-8")
    (task / "tests" / "criteria.py").write_text("WEIGHT = 1\n", encoding="utf-8")
    first = matrix_runner.hash_harbor_inputs(task)
    (task / "bundle").mkdir()
    (task / "bundle" / "clio.db").write_bytes(b"ignored generated state")
    assert matrix_runner.hash_harbor_inputs(task) == first
    environment = task / "environment"
    (environment / ".workbench" / "runtime").mkdir(parents=True)
    (environment / "workspace.md").write_text("agent workspace\n", encoding="utf-8")
    (environment / ".workbench" / "state.db").write_bytes(b"state one")
    (environment / ".workbench" / "runtime" / "server.py").write_text(
        "VERSION = 1\n", encoding="utf-8"
    )
    staged = matrix_runner.hash_harbor_inputs(task)
    assert staged.task_source_sha256 == first.task_source_sha256
    assert staged.environment_sha256 != first.environment_sha256
    (environment / ".workbench" / "state.db").write_bytes(b"state two")
    rematerialized = matrix_runner.hash_harbor_inputs(task)
    assert rematerialized.environment_sha256 != staged.environment_sha256
    (environment / ".workbench" / "runtime" / "server.py").write_text(
        "VERSION = 2\n", encoding="utf-8"
    )
    assert matrix_runner.hash_harbor_inputs(task).environment_sha256 != (
        rematerialized.environment_sha256
    )
    (task / "tests" / "criteria.py").write_text("WEIGHT = 2\n", encoding="utf-8")
    second = matrix_runner.hash_harbor_inputs(task)
    assert second.task_source_sha256 != first.task_source_sha256

    fingerprint = TrialFingerprint(
        git_revision="abc123",
        image_id="sha256:image",
        task_name="fee-dispute-reconstruction",
        task_source_sha256=second.task_source_sha256,
        environment_sha256=second.environment_sha256,
        gateway_version="1",
        harbor_version=HARBOR_VERSION,
        codex_version=CODEX_VERSION,
        agent_timeout_multiplier=AGENT_TIMEOUT_MULTIPLIER,
        model="openai/gpt-5.6-sol",
        enforced_provider_order=MODEL_PROVIDERS["openai/gpt-5.6-sol"],
    )
    assert smoke_is_reusable(fingerprint, fingerprint, smoke_valid=True)
    changed = fingerprint.model_copy(update={"image_id": "sha256:other"})
    assert not smoke_is_reusable(fingerprint, changed, smoke_valid=True)
    changed_timeout = fingerprint.model_copy(update={"agent_timeout_multiplier": 1.0})
    assert not smoke_is_reusable(fingerprint, changed_timeout, smoke_valid=True)
    assert not smoke_is_reusable(fingerprint, fingerprint, smoke_valid=False)


def test_derived_jobs_dir_under_a_worktree_is_refused() -> None:
    """A removable worktree must not silently receive paid trial artifacts.

    Deriving jobs_dir from the repository once destroyed ~$34 of settled
    diagnostics when the worktree was removed: every result.json,
    reward-details.json, and trajectory.json went with it.
    """

    base = dict(
        repository=Path("/tmp/repo"),
        tasks_root=Path("/tmp/repo/datasets/hartwell/tasks"),
        run_id="run-1",
        projected_worst_case_batch_usd=1.0,
    )
    worktree_jobs = Path("/home/u/.config/superpowers/worktrees/wb/branch/jobs")

    with pytest.raises(ValidationError):
        MatrixConfig(jobs_dir=worktree_jobs, jobs_dir_is_derived=True, **base)

    # An explicit --jobs-dir is an informed choice and is always honoured.
    explicit = MatrixConfig(jobs_dir=worktree_jobs, jobs_dir_is_derived=False, **base)
    assert explicit.jobs_dir == worktree_jobs

    durable = MatrixConfig(
        jobs_dir=Path("/tmp/repo/jobs"), jobs_dir_is_derived=True, **base
    )
    assert durable.jobs_dir == Path("/tmp/repo/jobs")


def test_run_provenance_preserves_criteria_and_tool_histogram(tmp_path: Path) -> None:
    """The scalars survived in *-matrix.json; these two did not.

    Reconstructing why a cell scored what it did needs the per-criterion
    table and the MCP tool histogram, so both are written somewhere git
    tracks rather than only into a gitignored jobs/ tree.
    """

    trial = tmp_path / "jobs" / "run-9-standard-drift" / "trial-1"
    (trial / "verifier").mkdir(parents=True)
    (trial / "agent").mkdir()
    (trial / "result.json").write_text(
        json.dumps(
            {
                "exception_info": None,
                "trial_name": "trial-1",
                "attempt": 2,
                "wall_time_sec": 812.5,
                "stop_reason": "finish",
                "config": {"agent": {"model_name": "luna"}},
                "verifier_result": {
                    "rewards": {"reward": 0.9094, "answer": 0.9094, "process": 0.5}
                },
            }
        ),
        encoding="utf-8",
    )
    (trial / "verifier" / "reward-details.json").write_text(
        json.dumps(
            {
                "answer": {
                    "score": 0.9094,
                    "kind": "programmatic",
                    "criteria": [
                        {"name": "version_audit", "value": 0.9375, "weight": 0.522},
                        {"name": "covering_emails", "value": 1.0, "weight": 0.2},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (trial / "agent" / "codex.txt").write_text(
        "tools.mcp__imanage__get_document_versions({})\n"
        "tools.mcp__imanage__get_document_versions({})\n"
        'call mcp__gmail__search_threads {"query": "x"}\n',
        encoding="utf-8",
    )

    provenance = matrix_provenance.collect_run_provenance(
        tmp_path / "jobs", run_id="run-9", git_revision="abc1234"
    )
    (cell,) = provenance.cells
    assert cell.task_name == "standard-drift"
    assert (cell.model_alias, cell.attempt, cell.answer) == ("luna", 2, 0.9094)
    assert cell.wall_time_sec == 812.5 and cell.stop_reason == "finish"
    assert cell.git_revision == "abc1234"
    assert {(c.name, c.value, c.weight) for c in cell.criteria} == {
        ("version_audit", 0.9375, 0.522),
        ("covering_emails", 1.0, 0.2),
    }
    assert cell.tool_calls == {
        "gmail.search_threads": 1,
        "imanage.get_document_versions": 2,
    }
    assert cell.tool_call_total == 3
    assert cell.artifacts_missing == ()

    docs_dir = tmp_path / "docs" / "runs" / "a-run"
    written = matrix_provenance.write_run_provenance(provenance, docs_dir)
    assert json.loads(written.read_text())["cells"][0]["tool_call_total"] == 3


def test_run_provenance_records_missing_artifacts_without_raising(
    tmp_path: Path,
) -> None:
    trial = tmp_path / "jobs" / "run-9-standard-drift" / "trial-1"
    trial.mkdir(parents=True)

    provenance = matrix_provenance.collect_run_provenance(
        tmp_path / "jobs", run_id="run-9"
    )
    (cell,) = provenance.cells
    assert cell.valid is False
    assert set(cell.artifacts_missing) == {
        "result.json",
        "verifier/reward-details.json",
        "agent/codex.txt",
    }


def test_cli_marks_a_defaulted_jobs_dir_as_derived() -> None:
    derived = parse_args(
        [
            "--run-id",
            "derived-run",
            "--repository",
            "/tmp/repo",
            "--projected-worst-case-batch-usd",
            "1.0",
        ]
    )
    assert derived.jobs_dir_is_derived is True

    explicit = parse_args(
        [
            "--run-id",
            "explicit-run",
            "--repository",
            "/tmp/repo",
            "--jobs-dir",
            "/var/harbor-jobs",
            "--projected-worst-case-batch-usd",
            "1.0",
        ]
    )
    assert explicit.jobs_dir_is_derived is False


# --- hermes: the gateway must be in config.yaml, not only in the env -----
#
# `hermes_agent` imports harbor, which is installed in the rollout runner's
# environment and not in this one. The three names it needs are stubbed
# rather than skipped: what is under test is the *shape of the YAML*, and a
# skipped test here is what let a whole tier score 0.000 three times.


def _hermes_class(monkeypatch: pytest.MonkeyPatch):
    """Import `HartwellHermes` against a stub harbor, and hand it back."""

    import sys
    import types

    import yaml

    for name in ("harbor", "harbor.agents", "harbor.agents.installed"):
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)

    base = types.ModuleType("harbor.agents.installed.base")
    base.BaseEnvironment = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "harbor.agents.installed.base", base)

    class _Hermes:
        """Harbor's own builder: a flat model id and no endpoint at all."""

        @staticmethod
        def _build_config_yaml(model: str) -> str:
            return yaml.dump(
                {
                    "model": model,
                    "provider": "auto",
                    "agent": {"max_turns": 90},
                    "delegation": {"max_iterations": 50},
                }
            )

    hermes_module = types.ModuleType("harbor.agents.installed.hermes")
    hermes_module.Hermes = _Hermes  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "harbor.agents.installed.hermes", hermes_module)
    monkeypatch.delitem(
        sys.modules, "adapters.harbor_matrix.hermes_agent", raising=False
    )

    from adapters.harbor_matrix.hermes_agent import HartwellHermes

    class _Fake(HartwellHermes):  # type: ignore[misc]
        def __init__(self, env: dict[str, str]) -> None:
            self._env = env

        def _get_env(self, key: str) -> str | None:
            return self._env.get(key)

    return _Fake


HERMES_GATEWAY_URL = "http://host.docker.internal:51234/v1"


def test_hermes_config_carries_the_gateway_endpoint_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sub-agents read this file and nothing else.

    A trial's log showed the main agent planning correctly and every one of
    its eight sub-agents dying in under three seconds against
    `https://openrouter.ai/api/v1` with `Missing Authentication header` --
    no endpoint, no token, because `config.yaml` named neither. Both belong
    here, and only `provider: custom` makes hermes read either: the key is
    sourced from `model.api_key` under that provider alone, and a
    non-loopback `base_url` is rejected under any other.
    """

    import yaml

    hermes = _hermes_class(monkeypatch)
    written = yaml.safe_load(
        hermes(
            {
                "OPENAI_BASE_URL": HERMES_GATEWAY_URL,
                "HARTWELL_GATEWAY_TOKEN": "ephemeral-container-secret",
            }
        )._build_config_yaml("openai/gpt-5.6-sol")
    )

    assert written["model"] == {
        "provider": "custom",
        "default": "openai/gpt-5.6-sol",
        "base_url": HERMES_GATEWAY_URL,
        "api_key": "ephemeral-container-secret",
        # Pinned, not inferred: the gateway serves chat completions and
        # responses and nothing else.
        "api_mode": "chat_completions",
    }
    assert written["provider"] == "custom"
    # Harbor's own settings survive; this rewrites the model, not the file.
    assert written["agent"]["max_turns"] == 90
    assert written["delegation"]["max_iterations"] == 50


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({}, id="neither"),
        pytest.param({"OPENAI_BASE_URL": HERMES_GATEWAY_URL}, id="endpoint-only"),
        pytest.param({"HARTWELL_GATEWAY_TOKEN": "secret"}, id="token-only"),
    ],
)
def test_hermes_config_declines_a_half_configured_custom_provider(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Without both halves, leave harbor's shape alone.

    A credential and its endpoint are one setting. Writing `provider:
    custom` with only one of them produces a config that fails later and
    less legibly than the one it replaced -- so the branch that declines to
    fire is tested here alongside the one that does.
    """

    import yaml

    hermes = _hermes_class(monkeypatch)
    written = yaml.safe_load(hermes(env)._build_config_yaml("openai/gpt-5.6-sol"))

    assert written["provider"] == "openrouter"
    assert written["model"] == "openai/gpt-5.6-sol"

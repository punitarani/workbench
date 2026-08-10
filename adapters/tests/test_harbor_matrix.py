import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from workbench.adapters.harbor_matrix.cli import parse_args
from workbench.adapters.harbor_matrix.gateway import (
    GatewayConfig,
    ProviderGateway,
)
from workbench.adapters.harbor_matrix.runner import (
    CODEX_VERSION,
    HARBOR_VERSION,
    MODEL_ALIASES,
    TASK_ORDER,
    BudgetExceededError,
    CompletedCommand,
    CreditBudget,
    CreditMeter,
    CreditSnapshot,
    HarborRunError,
    MatrixConfig,
    MatrixRunner,
    TrialFingerprint,
    build_harbor_command,
    classify_trial_result,
    hash_task_content,
    smoke_is_reusable,
    validate_batch_outcomes,
    validate_harbor_version,
)
from workbench.adapters.harness.openrouter_client import MODEL_PROVIDERS


@pytest.fixture
def gateway_config() -> GatewayConfig:
    return GatewayConfig(
        openrouter_api_key="openrouter-host-secret",
        gateway_token="ephemeral-container-secret",
        bind_host="127.0.0.1",
        port=0,
        upstream_url="https://openrouter.test/api/v1/responses",
    )


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

    caplog.set_level(logging.INFO, logger="workbench.adapters.harbor_matrix.gateway")
    transport = httpx.MockTransport(upstream)
    gateway = ProviderGateway(gateway_config, upstream_transport=transport)
    async with gateway:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{gateway.local_url}/v1/responses",
                headers={"Authorization": "Bearer ephemeral-container-secret"},
                json={
                    "model": "glm-5.2",
                    "input": "private client request",
                    "stream": False,
                },
            )

    assert response.status_code == 200
    assert response.headers["x-upstream"] == "kept"
    assert response.json() == {"id": "response-1", "status": "completed"}
    assert seen["authorization"] == "Bearer openrouter-host-secret"
    assert seen["body"] == {
        "model": "z-ai/glm-5.2",
        "input": "private client request",
        "stream": False,
        "provider": {
            "order": ["baidu/fp8", "novita/fp8", "streamlake/fp8"],
            "allow_fallbacks": False,
        },
    }
    assert gateway.provenance[0].model == "z-ai/glm-5.2"
    assert gateway.provenance[0].provider_order == MODEL_PROVIDERS["z-ai/glm-5.2"]
    log_text = caplog.text
    assert "z-ai/glm-5.2" in log_text
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
        assert body["model"] == "deepseek/deepseek-v4-flash-0731"
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
                json={"model": "deepseek-v4-flash-0731", "stream": True},
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["x-stream"] == "yes"
                assert await response.aread() == b"data: one\n\ndata: [DONE]\n\n"
            error = await client.post(
                f"{gateway.local_url}/v1/responses",
                headers=headers,
                json={"model": "deepseek-v4-flash-0731"},
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
                    json={"model": "gpt-5.6-luna", "input": "secret"},
                )
                assert response.status_code == 401
                assert upstream_calls == 0
            raise RuntimeError("intentional")

    assert not gateway.running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.post(gateway.local_url, timeout=0.1)


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
        gateway_token="ephemeral-only",
    )

    assert command[:3] == ("harbor", "run", "-p")
    assert command.count("-m") == 3
    for alias in MODEL_ALIASES:
        assert alias in command
    assert ("--ak", f"version={CODEX_VERSION}") == (
        command[command.index("--ak")],
        command[command.index("--ak") + 1],
    )
    assert "OPENAI_BASE_URL=http://host.docker.internal:43121/v1" in command
    assert "OPENAI_API_KEY=ephemeral-only" in command
    assert "host.docker.internal" in command
    assert command[command.index("-n") + 1] == "8"
    assert command[command.index("--n-concurrent-agents") + 1] == "8"
    assert command[command.index("-k") + 1] == "3"
    assert command[command.index("--job-name") + 1] == (
        "final-matrix-01-fee-dispute-reconstruction"
    )
    assert validate_harbor_version("harbor 0.18.0\n") == HARBOR_VERSION
    with pytest.raises(ValueError, match="0.18.0"):
        validate_harbor_version("harbor 0.19.0")


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


def test_budget_enforces_project_cap_and_reserve() -> None:
    budget = CreditBudget()
    credits = CreditSnapshot(total_credits=100, total_usage=50.0)
    budget.assert_can_launch(credits, projected_worst_case_usd=5.7)
    with pytest.raises(BudgetExceededError):
        budget.assert_can_launch(credits, projected_worst_case_usd=5.714)
    assert budget.cap_usage == pytest.approx(57.2139)


async def test_credit_meter_uses_authoritative_endpoint_without_leaking_key() -> None:
    seen_authorization = ""

    async def credits(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers["authorization"]
        assert str(request.url) == "https://openrouter.ai/api/v1/credits"
        return httpx.Response(
            200,
            json={"data": {"total_credits": 100.0, "total_usage": 40.433}},
        )

    meter = CreditMeter("meter-host-secret", transport=httpx.MockTransport(credits))
    try:
        snapshot = await meter.query()
    finally:
        await meter.aclose()

    assert snapshot == CreditSnapshot(total_credits=100.0, total_usage=40.433)
    assert seen_authorization == "Bearer meter-host-secret"


class FakeCreditMeter:
    def __init__(self) -> None:
        self.queries = 0

    async def query(self) -> CreditSnapshot:
        snapshot = CreditSnapshot(
            total_credits=100,
            total_usage=40.0 + (self.queries * 0.25),
        )
        self.queries += 1
        return snapshot


class FakeCommands:
    def __init__(self) -> None:
        self.harbor_tasks: list[str] = []

    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        if command == ("harbor", "--version"):
            return CompletedCommand(returncode=0, stdout="harbor 0.18.0\n")
        if command == ("git", "rev-parse", "HEAD"):
            return CompletedCommand(returncode=0, stdout="deadbeef\n")
        if command[:3] == ("docker", "image", "inspect"):
            return CompletedCommand(returncode=0, stdout="sha256:image\n")
        task_name = Path(command[command.index("-p") + 1]).name
        self.harbor_tasks.append(task_name)
        jobs_dir = Path(command[command.index("-o") + 1])
        job_name = command[command.index("--job-name") + 1]
        attempts = int(command[command.index("-k") + 1])
        aliases = [
            command[index + 1] for index, value in enumerate(command) if value == "-m"
        ]
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
                                    "reward": 0.2,
                                    "answer": 0.2,
                                    "process": 0.8,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
        return CompletedCommand(returncode=0)


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

    assert tuple(commands.harbor_tasks) == TASK_ORDER
    assert meter.queries == 1 + len(TASK_ORDER)
    assert [batch.task_name for batch in report.batches] == list(TASK_ORDER)
    assert all(len(batch.outcomes) == 9 for batch in report.batches)
    assert all(outcome.valid for batch in report.batches for outcome in batch.outcomes)
    persisted = json.loads(
        (config.jobs_dir / "offline-matrix-matrix.json").read_text(encoding="utf-8")
    )
    assert len(persisted["batches"]) == 8


def test_fingerprint_is_content_sensitive_and_smoke_requires_exact_match(
    tmp_path: Path,
) -> None:
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "task.toml").write_text("version = '1.0'\n", encoding="utf-8")
    (task / "tests" / "criteria.py").write_text("WEIGHT = 1\n", encoding="utf-8")
    first_hash = hash_task_content(task)
    (task / "bundle").mkdir()
    (task / "bundle" / "clio.db").write_bytes(b"ignored generated state")
    assert hash_task_content(task) == first_hash
    (task / "tests" / "criteria.py").write_text("WEIGHT = 2\n", encoding="utf-8")
    second_hash = hash_task_content(task)
    assert second_hash != first_hash

    fingerprint = TrialFingerprint(
        git_revision="abc123",
        image_id="sha256:image",
        task_name="fee-dispute-reconstruction",
        task_content_sha256=second_hash,
        gateway_version="1",
        harbor_version=HARBOR_VERSION,
        codex_version=CODEX_VERSION,
        model="z-ai/glm-5.2",
        provider_order=MODEL_PROVIDERS["z-ai/glm-5.2"],
    )
    assert smoke_is_reusable(fingerprint, fingerprint, smoke_valid=True)
    changed = fingerprint.model_copy(update={"image_id": "sha256:other"})
    assert not smoke_is_reusable(fingerprint, changed, smoke_valid=True)
    assert not smoke_is_reusable(fingerprint, fingerprint, smoke_valid=False)

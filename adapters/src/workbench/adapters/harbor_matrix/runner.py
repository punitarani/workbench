import asyncio
import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    SecretStr,
    StrictFloat,
    StrictInt,
    ValidationError,
)

from workbench.adapters.harbor_matrix.gateway import (
    GATEWAY_VERSION,
    GatewayConfig,
    GatewayProvenance,
    ProviderGateway,
)
from workbench.adapters.harbor_matrix.gateway import (
    MODEL_ALIASES as ALIAS_TO_MODEL,
)
from workbench.adapters.harness.openrouter_client import MODEL_PROVIDERS

HARBOR_VERSION = "0.18.0"
CODEX_VERSION = "0.147.0"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
MODEL_ALIASES = tuple(ALIAS_TO_MODEL)
TASK_ORDER = (
    "fee-dispute-reconstruction",
    "client-departure-postmortem",
    "billing-hygiene-audit",
    "second-read-audit",
    "visitor-log-audit",
    "operative-deadline",
    "standard-drift",
    "vanished-clause",
)
IGNORED_TASK_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "bundle",
    "environment",
    "jobs",
}


class MatrixConfig(BaseModel):
    repository: Path
    tasks_root: Path
    jobs_dir: Path
    run_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    attempts: int = Field(default=3, ge=1)
    concurrency: int = Field(default=8, ge=1, le=8)
    projected_worst_case_batch_usd: FiniteFloat = Field(gt=0)
    gateway_bind_host: str = "0.0.0.0"


class CreditSnapshot(BaseModel):
    total_credits: FiniteFloat = Field(ge=0)
    total_usage: FiniteFloat = Field(ge=0)


class CreditsEnvelope(BaseModel):
    data: CreditSnapshot


class CreditBudget(BaseModel):
    baseline_usage: FiniteFloat = 32.2139
    project_cap_usd: FiniteFloat = 25.0
    reserve_usd: FiniteFloat = 1.5

    @property
    def cap_usage(self) -> float:
        return float(self.baseline_usage + self.project_cap_usd)

    def assert_can_launch(
        self,
        credits: CreditSnapshot,
        *,
        projected_worst_case_usd: float,
    ) -> None:
        projected = credits.total_usage + projected_worst_case_usd + self.reserve_usd
        if projected > self.cap_usage:
            available = max(
                0.0, self.cap_usage - credits.total_usage - self.reserve_usd
            )
            raise BudgetExceededError(
                "projected batch exceeds the Hartwell cap: "
                f"${projected_worst_case_usd:.4f} projected, "
                f"${available:.4f} available after reserve"
            )


class CreditMeter:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = SecretStr(api_key)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            transport=transport,
        )

    async def query(self) -> CreditSnapshot:
        response = await self._client.get(
            OPENROUTER_CREDITS_URL,
            headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
        )
        if response.status_code != 200:
            raise CreditMeterError(
                f"OpenRouter credits meter returned {response.status_code}"
            )
        try:
            return CreditsEnvelope.model_validate_json(response.content).data
        except ValidationError as error:
            raise CreditMeterError(
                "OpenRouter credits meter response was malformed"
            ) from error

    async def aclose(self) -> None:
        await self._client.aclose()


class TrialFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    git_revision: str
    image_id: str
    task_name: str
    task_content_sha256: str
    gateway_version: str
    harbor_version: str
    codex_version: str
    model: str
    provider_order: tuple[str, ...]


class VerifierRewards(BaseModel):
    reward: StrictFloat | StrictInt
    answer: StrictFloat | StrictInt
    process: StrictFloat | StrictInt


class VerifierResult(BaseModel):
    rewards: VerifierRewards


class AgentConfig(BaseModel):
    model_name: str | None = None


class TrialConfig(BaseModel):
    agent: AgentConfig | None = None


class AgentInfo(BaseModel):
    version: str | None = None


class TrialResultEnvelope(BaseModel):
    exception_info: object | None
    verifier_result: VerifierResult | None
    config: TrialConfig | None = None
    agent_info: AgentInfo | None = None
    trial_name: str | None = None


class TrialOutcome(BaseModel):
    path: Path
    valid: bool
    reason: str | None = None
    trial_name: str | None = None
    model_alias: str | None = None
    agent_version: str | None = None
    reward: float | None = None
    answer: float | None = None
    process: float | None = None


class CompletedCommand(BaseModel):
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand: ...


class CreditReader(Protocol):
    async def query(self) -> CreditSnapshot: ...


class SubprocessCommandRunner:
    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return CompletedCommand(
            returncode=process.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )


class BatchReport(BaseModel):
    task_name: str
    job_name: str
    usage_before: float
    usage_after: float
    metered_cost_usd: float
    projected_worst_case_usd: float
    fingerprints: tuple[TrialFingerprint, ...]
    outcomes: tuple[TrialOutcome, ...]


class MatrixReport(BaseModel):
    run_id: str
    baseline_usage: float
    cap_usage: float
    batches: tuple[BatchReport, ...]
    gateway_provenance: tuple[GatewayProvenance, ...]


class BudgetExceededError(RuntimeError):
    pass


class CreditMeterError(RuntimeError):
    pass


class HarborRunError(RuntimeError):
    pass


def validate_harbor_version(output: str) -> str:
    tokens = output.strip().split()
    version = tokens[-1] if tokens else ""
    if version != HARBOR_VERSION:
        raise ValueError(
            f"Harbor {HARBOR_VERSION} is required; "
            f"version output was {output.strip()!r}"
        )
    return version


def build_harbor_command(
    config: MatrixConfig,
    task_name: str,
    *,
    gateway_port: int,
    gateway_token: str,
    attempts: int | None = None,
    model_aliases: tuple[str, ...] = MODEL_ALIASES,
) -> tuple[str, ...]:
    if task_name not in TASK_ORDER:
        raise ValueError(f"unknown Hartwell matrix task: {task_name}")
    task_number = TASK_ORDER.index(task_name) + 1
    job_name = f"{config.run_id}-{task_number:02d}-{task_name}"
    command = [
        "harbor",
        "run",
        "-p",
        str(config.tasks_root / task_name),
        "-a",
        "codex",
    ]
    for alias in model_aliases:
        if alias not in ALIAS_TO_MODEL:
            raise ValueError(f"unsupported Harbor model alias: {alias}")
        command.extend(("-m", alias))
    command.extend(
        (
            "-k",
            str(config.attempts if attempts is None else attempts),
            "-n",
            str(config.concurrency),
            "--n-concurrent-agents",
            str(config.concurrency),
            "--ak",
            f"version={CODEX_VERSION}",
            "--ae",
            f"OPENAI_BASE_URL=http://host.docker.internal:{gateway_port}/v1",
            "--ae",
            f"OPENAI_API_KEY={gateway_token}",
            "--allow-agent-host",
            "host.docker.internal",
            "--max-retries",
            "0",
            "-y",
            "-o",
            str(config.jobs_dir),
            "--job-name",
            job_name,
        )
    )
    return tuple(command)


def redact_harbor_command(command: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        "OPENAI_API_KEY=<ephemeral-redacted>"
        if argument.startswith("OPENAI_API_KEY=")
        else argument
        for argument in command
    )


def hash_task_content(task_dir: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in task_dir.rglob("*")
        if path.is_file()
        and not IGNORED_TASK_PARTS.intersection(path.relative_to(task_dir).parts)
    )
    for path in paths:
        relative = path.relative_to(task_dir).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def classify_trial_result(path: Path) -> TrialOutcome:
    try:
        result = TrialResultEnvelope.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as error:
        return TrialOutcome(path=path, valid=False, reason=type(error).__name__)
    model_alias = (
        result.config.agent.model_name
        if result.config is not None and result.config.agent is not None
        else None
    )
    agent_version = result.agent_info.version if result.agent_info is not None else None
    if result.exception_info is not None:
        return TrialOutcome(
            path=path,
            valid=False,
            reason=_exception_name(result.exception_info),
            trial_name=result.trial_name,
            model_alias=model_alias,
            agent_version=agent_version,
        )
    if result.verifier_result is None:
        return TrialOutcome(
            path=path,
            valid=False,
            reason="missing verifier_result",
            trial_name=result.trial_name,
            model_alias=model_alias,
            agent_version=agent_version,
        )
    rewards = result.verifier_result.rewards
    values = (float(rewards.reward), float(rewards.answer), float(rewards.process))
    if not all(math.isfinite(value) for value in values):
        return TrialOutcome(
            path=path,
            valid=False,
            reason="non-finite verifier reward",
            trial_name=result.trial_name,
            model_alias=model_alias,
            agent_version=agent_version,
        )
    return TrialOutcome(
        path=path,
        valid=True,
        trial_name=result.trial_name,
        model_alias=model_alias,
        agent_version=agent_version,
        reward=values[0],
        answer=values[1],
        process=values[2],
    )


def load_trial_outcomes(job_dir: Path) -> tuple[TrialOutcome, ...]:
    return tuple(
        classify_trial_result(path) for path in sorted(job_dir.glob("*/result.json"))
    )


def validate_batch_outcomes(
    outcomes: tuple[TrialOutcome, ...], *, attempts: int
) -> None:
    invalid = [outcome for outcome in outcomes if not outcome.valid]
    if invalid:
        raise HarborRunError(f"Harbor batch has {len(invalid)} invalid trials")
    actual = Counter(outcome.model_alias for outcome in outcomes)
    expected = Counter({alias: attempts for alias in MODEL_ALIASES})
    if actual != expected:
        raise HarborRunError(
            "Harbor batch did not produce the required model-attempt cells: "
            f"expected {dict(expected)}, got {dict(actual)}"
        )
    wrong_versions = Counter(outcome.agent_version for outcome in outcomes)
    if wrong_versions != Counter({CODEX_VERSION: len(outcomes)}):
        raise HarborRunError(
            f"Harbor batch did not run Codex {CODEX_VERSION}: "
            f"got {dict(wrong_versions)}"
        )


def smoke_is_reusable(
    smoke: TrialFingerprint,
    final: TrialFingerprint,
    *,
    smoke_valid: bool,
) -> bool:
    return smoke_valid and smoke == final


def build_trial_fingerprints(
    *,
    git_revision: str,
    image_id: str,
    task_name: str,
    task_content_sha256: str,
) -> tuple[TrialFingerprint, ...]:
    return tuple(
        TrialFingerprint(
            git_revision=git_revision,
            image_id=image_id,
            task_name=task_name,
            task_content_sha256=task_content_sha256,
            gateway_version=GATEWAY_VERSION,
            harbor_version=HARBOR_VERSION,
            codex_version=CODEX_VERSION,
            model=full_model,
            provider_order=MODEL_PROVIDERS[full_model],
        )
        for full_model in ALIAS_TO_MODEL.values()
    )


class MatrixRunner:
    def __init__(
        self,
        config: MatrixConfig,
        *,
        openrouter_api_key: str,
        gateway_token: str,
        commands: CommandRunner | None = None,
        credit_meter: CreditReader | None = None,
        gateway_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._openrouter_api_key = SecretStr(openrouter_api_key)
        self._gateway_token = SecretStr(gateway_token)
        self._commands = commands or SubprocessCommandRunner()
        if credit_meter is None:
            self._owned_credit_meter: CreditMeter | None = CreditMeter(
                openrouter_api_key
            )
            self._credit_meter: CreditReader = self._owned_credit_meter
        else:
            self._owned_credit_meter = None
            self._credit_meter = credit_meter
        self._gateway_transport = gateway_transport
        self._budget = CreditBudget()

    async def run(self) -> MatrixReport:
        harbor_version = await self._commands.run(
            ("harbor", "--version"), cwd=self.config.repository
        )
        if harbor_version.returncode != 0:
            raise HarborRunError("could not read the Harbor version")
        validate_harbor_version(harbor_version.stdout)
        git_revision = await self._capture(("git", "rev-parse", "HEAD"), "git revision")
        image_id = await self._capture(
            ("docker", "image", "inspect", "--format", "{{.Id}}", "workbench:dev"),
            "workbench:dev image ID",
        )
        credits = await self._credit_meter.query()
        forecast = float(self.config.projected_worst_case_batch_usd)
        batches: list[BatchReport] = []
        gateway = ProviderGateway(
            GatewayConfig(
                openrouter_api_key=self._openrouter_api_key,
                gateway_token=self._gateway_token,
                bind_host=self.config.gateway_bind_host,
                port=0,
            ),
            upstream_transport=self._gateway_transport,
        )
        try:
            async with gateway:
                for task_name in TASK_ORDER:
                    self._budget.assert_can_launch(
                        credits, projected_worst_case_usd=forecast
                    )
                    task_dir = self.config.tasks_root / task_name
                    task_hash = hash_task_content(task_dir)
                    fingerprints = build_trial_fingerprints(
                        git_revision=git_revision,
                        image_id=image_id,
                        task_name=task_name,
                        task_content_sha256=task_hash,
                    )
                    command = build_harbor_command(
                        self.config,
                        task_name,
                        gateway_port=gateway.port,
                        gateway_token=self._gateway_token.get_secret_value(),
                    )
                    completed = await self._commands.run(
                        command, cwd=self.config.repository
                    )
                    after = await self._credit_meter.query()
                    metered_cost = max(0.0, after.total_usage - credits.total_usage)
                    job_name = command[command.index("--job-name") + 1]
                    outcomes = load_trial_outcomes(self.config.jobs_dir / job_name)
                    batch = BatchReport(
                        task_name=task_name,
                        job_name=job_name,
                        usage_before=float(credits.total_usage),
                        usage_after=float(after.total_usage),
                        metered_cost_usd=metered_cost,
                        projected_worst_case_usd=forecast,
                        fingerprints=fingerprints,
                        outcomes=outcomes,
                    )
                    batches.append(batch)
                    report = MatrixReport(
                        run_id=self.config.run_id,
                        baseline_usage=float(self._budget.baseline_usage),
                        cap_usage=self._budget.cap_usage,
                        batches=tuple(batches),
                        gateway_provenance=tuple(gateway.provenance),
                    )
                    self._write_report(report)
                    credits = after
                    forecast = max(forecast, metered_cost)
                    if completed.returncode != 0:
                        raise HarborRunError(
                            f"Harbor batch {task_name} exited {completed.returncode}"
                        )
                    validate_batch_outcomes(outcomes, attempts=self.config.attempts)
        finally:
            if self._owned_credit_meter is not None:
                await self._owned_credit_meter.aclose()
        return MatrixReport(
            run_id=self.config.run_id,
            baseline_usage=float(self._budget.baseline_usage),
            cap_usage=self._budget.cap_usage,
            batches=tuple(batches),
            gateway_provenance=tuple(gateway.provenance),
        )

    async def _capture(self, command: tuple[str, ...], label: str) -> str:
        completed = await self._commands.run(command, cwd=self.config.repository)
        value = completed.stdout.strip()
        if completed.returncode != 0 or not value:
            raise HarborRunError(f"could not resolve {label}")
        return value

    def _write_report(self, report: MatrixReport) -> None:
        self.config.jobs_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.jobs_dir / f"{self.config.run_id}-matrix.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def _exception_name(exception_info: object) -> str:
    if isinstance(exception_info, dict):
        for key in ("exception_type", "type", "name"):
            value = exception_info.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(exception_info, str) and exception_info:
        return exception_info
    return "trial exception"

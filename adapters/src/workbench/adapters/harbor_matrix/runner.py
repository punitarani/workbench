import asyncio
import hashlib
import math
import stat
from collections import Counter
from pathlib import Path
from typing import Literal, Protocol

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
IGNORED_TASK_SOURCE_PARTS = {
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
    attempts: Literal[3] = 3
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

    def metered_cost(self, before: CreditSnapshot, after: CreditSnapshot) -> float:
        if after.total_usage < before.total_usage:
            raise CreditMeterError(
                "OpenRouter total_usage decreased between meter snapshots"
            )
        return float(after.total_usage - before.total_usage)

    def assert_observed_within_cap(self, credits: CreditSnapshot) -> None:
        if credits.total_usage > self.cap_usage:
            raise BudgetExceededError(
                "observed OpenRouter usage exceeded the Hartwell project cap: "
                f"${credits.total_usage:.4f} used versus ${self.cap_usage:.4f} cap"
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
    task_source_sha256: str
    environment_sha256: str
    gateway_version: str
    harbor_version: str
    codex_version: str
    model: str
    enforced_provider_order: tuple[str, ...]


class HarborInputHashes(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_source_sha256: str
    environment_sha256: str


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


class GatewaySequenceSpan(BaseModel):
    start_exclusive: int = Field(ge=0)
    end_inclusive: int = Field(ge=0)


class LaunchReport(BaseModel):
    sequence: int = Field(ge=1)
    phase: Literal["smoke", "additional", "matrix"]
    task_name: str
    job_name: str
    attempts_per_model: int = Field(ge=1, le=3)
    enforced_model_routes: dict[str, tuple[str, ...]]
    gateway_sequences: GatewaySequenceSpan
    usage_before: float
    usage_after: float
    metered_cost_usd: float
    projected_worst_case_usd: float
    valid: bool
    failure: str | None = None


class TrialRecord(BaseModel):
    attempt: int | None = Field(default=None, ge=1, le=3)
    source_job_name: str
    phase: Literal["smoke", "additional", "matrix"]
    fingerprint: TrialFingerprint | None
    outcome: TrialOutcome


class SmokeReport(BaseModel):
    task_name: Literal["fee-dispute-reconstruction"]
    job_name: str
    valid: bool
    failure: str | None = None
    trials: tuple[TrialRecord, ...]
    launch_sequence: int


class BatchReport(BaseModel):
    task_name: str
    trials: tuple[TrialRecord, ...]
    launch_sequences: tuple[int, ...]
    valid: bool
    failure: str | None = None


class MatrixReport(BaseModel):
    run_id: str
    baseline_usage: float
    cap_usage: float
    smoke: SmokeReport | None = None
    batches: tuple[BatchReport, ...]
    launches: tuple[LaunchReport, ...]
    gateway_provenance: tuple[GatewayProvenance, ...]
    failure: str | None = None


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
    job_label: str | None = None,
) -> tuple[str, ...]:
    if task_name not in TASK_ORDER:
        raise ValueError(f"unknown Hartwell matrix task: {task_name}")
    task_number = TASK_ORDER.index(task_name) + 1
    label = f"-{job_label}" if job_label is not None else ""
    job_name = f"{config.run_id}{label}-{task_number:02d}-{task_name}"
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
    return _hash_tree(task_dir, ignored_top_level=IGNORED_TASK_SOURCE_PARTS)


def hash_harbor_inputs(task_dir: Path) -> HarborInputHashes:
    """Hash task source and the exact environment tree Harbor uploads.

    ``bundle/`` is build input for ``environment/`` and is not referenced by
    ``task.toml`` or passed separately to Harbor. The materialized
    ``environment/`` tree is hashed without exclusions, including workspace
    documents, staged databases, runtime files, symlinks, and mode bits.
    """

    return HarborInputHashes(
        task_source_sha256=hash_task_content(task_dir),
        environment_sha256=_hash_tree(task_dir / "environment"),
    )


def _hash_tree(root: Path, *, ignored_top_level: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(b"missing\0" if not root.exists() else b"tree\0")
    if not root.exists():
        return digest.hexdigest()
    ignored = ignored_top_level or set()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.relative_to(root).parts[0] not in ignored
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        metadata = path.lstat()
        digest.update(stat.S_IMODE(metadata.st_mode).to_bytes(4, "big"))
        if path.is_symlink():
            digest.update(b"link\0")
            target = path.readlink().as_posix().encode()
            digest.update(len(target).to_bytes(8, "big"))
            digest.update(target)
        elif path.is_dir():
            digest.update(b"directory\0")
        elif path.is_file():
            digest.update(b"file\0")
            content = path.read_bytes()
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        else:
            digest.update(b"other\0")
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
    if not all(0.0 <= value <= 1.0 for value in values):
        return TrialOutcome(
            path=path,
            valid=False,
            reason="verifier reward outside [0, 1]",
            trial_name=result.trial_name,
            model_alias=model_alias,
            agent_version=agent_version,
        )
    if values[0] != values[1]:
        return TrialOutcome(
            path=path,
            valid=False,
            reason="reward does not equal answer",
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
    task_source_sha256: str,
    environment_sha256: str,
) -> tuple[TrialFingerprint, ...]:
    return tuple(
        TrialFingerprint(
            git_revision=git_revision,
            image_id=image_id,
            task_name=task_name,
            task_source_sha256=task_source_sha256,
            environment_sha256=environment_sha256,
            gateway_version=GATEWAY_VERSION,
            harbor_version=HARBOR_VERSION,
            codex_version=CODEX_VERSION,
            model=full_model,
            enforced_provider_order=MODEL_PROVIDERS[full_model],
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
        credits = await self._credit_meter.query()
        forecast = float(self.config.projected_worst_case_batch_usd)
        smoke: SmokeReport | None = None
        batches: list[BatchReport] = []
        launches: list[LaunchReport] = []
        failure: str | None = None
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
                try:
                    fee_task = TASK_ORDER[0]
                    smoke_fingerprints = await self._resolve_fingerprints(fee_task)
                    smoke_execution = await self._execute_launch(
                        gateway=gateway,
                        credits=credits,
                        forecast=forecast,
                        task_name=fee_task,
                        attempts=1,
                        phase="smoke",
                        job_label="smoke",
                        sequence=1,
                    )
                    launches.append(smoke_execution.launch)
                    credits = smoke_execution.credits_after
                    forecast = max(forecast, smoke_execution.launch.metered_cost_usd)
                    smoke_trials = _build_trial_records(
                        smoke_execution.outcomes,
                        smoke_fingerprints,
                        job_name=smoke_execution.launch.job_name,
                        phase="smoke",
                        first_attempt=1,
                    )
                    smoke = SmokeReport(
                        task_name="fee-dispute-reconstruction",
                        job_name=smoke_execution.launch.job_name,
                        valid=False,
                        trials=smoke_trials,
                        launch_sequence=smoke_execution.launch.sequence,
                    )
                    smoke_failure = _launch_failure(smoke_execution)
                    if smoke_failure is None:
                        try:
                            validate_batch_outcomes(
                                smoke_execution.outcomes, attempts=1
                            )
                        except HarborRunError as error:
                            smoke_failure = f"fee smoke invalid: {error}"
                    try:
                        final_fee_fingerprints = await self._resolve_fingerprints(
                            fee_task
                        )
                    except HarborRunError as error:
                        final_fee_fingerprints = smoke_fingerprints
                        smoke_failure = f"fee smoke fingerprint check failed: {error}"
                    if smoke_failure is None:
                        if not _fingerprint_sets_reusable(
                            smoke_fingerprints,
                            final_fee_fingerprints,
                            smoke_valid=True,
                        ):
                            smoke_failure = (
                                "fee smoke fingerprint does not match the final fee "
                                "config"
                            )
                    smoke = smoke.model_copy(
                        update={
                            "valid": smoke_failure is None,
                            "failure": smoke_failure,
                        }
                    )
                    launches[-1] = launches[-1].model_copy(
                        update={
                            "valid": smoke_failure is None,
                            "failure": smoke_failure,
                        }
                    )
                    self._write_report(
                        self._report(smoke, batches, launches, gateway, smoke_failure)
                    )
                    if smoke_failure is not None:
                        if smoke_execution.post_meter_error is not None:
                            raise smoke_execution.post_meter_error
                        raise HarborRunError(smoke_failure)

                    fee_execution = await self._execute_launch(
                        gateway=gateway,
                        credits=credits,
                        forecast=forecast,
                        task_name=fee_task,
                        attempts=2,
                        phase="additional",
                        job_label="additional",
                        sequence=2,
                    )
                    launches.append(fee_execution.launch)
                    credits = fee_execution.credits_after
                    forecast = max(forecast, fee_execution.launch.metered_cost_usd)
                    fee_trials = smoke_trials + _build_trial_records(
                        fee_execution.outcomes,
                        final_fee_fingerprints,
                        job_name=fee_execution.launch.job_name,
                        phase="additional",
                        first_attempt=2,
                    )
                    fee_outcomes = smoke_execution.outcomes + fee_execution.outcomes
                    fee_failure = _launch_failure(fee_execution)
                    if fee_failure is None:
                        try:
                            validate_batch_outcomes(fee_outcomes, attempts=3)
                        except HarborRunError as error:
                            fee_failure = str(error)
                    batches.append(
                        BatchReport(
                            task_name=fee_task,
                            trials=fee_trials,
                            launch_sequences=(1, 2),
                            valid=fee_failure is None,
                            failure=fee_failure,
                        )
                    )
                    launches[-1] = launches[-1].model_copy(
                        update={
                            "valid": fee_failure is None,
                            "failure": fee_failure,
                        }
                    )
                    self._write_report(
                        self._report(smoke, batches, launches, gateway, fee_failure)
                    )
                    if fee_failure is not None:
                        if fee_execution.post_meter_error is not None:
                            raise fee_execution.post_meter_error
                        raise HarborRunError(f"Harbor fee batch invalid: {fee_failure}")

                    for sequence, task_name in enumerate(TASK_ORDER[1:], start=3):
                        fingerprints = await self._resolve_fingerprints(task_name)
                        execution = await self._execute_launch(
                            gateway=gateway,
                            credits=credits,
                            forecast=forecast,
                            task_name=task_name,
                            attempts=3,
                            phase="matrix",
                            job_label=None,
                            sequence=sequence,
                        )
                        launches.append(execution.launch)
                        credits = execution.credits_after
                        forecast = max(forecast, execution.launch.metered_cost_usd)
                        trials = _build_trial_records(
                            execution.outcomes,
                            fingerprints,
                            job_name=execution.launch.job_name,
                            phase="matrix",
                            first_attempt=1,
                        )
                        batch_failure = _launch_failure(execution)
                        if batch_failure is None:
                            try:
                                validate_batch_outcomes(execution.outcomes, attempts=3)
                            except HarborRunError as error:
                                batch_failure = str(error)
                        batches.append(
                            BatchReport(
                                task_name=task_name,
                                trials=trials,
                                launch_sequences=(sequence,),
                                valid=batch_failure is None,
                                failure=batch_failure,
                            )
                        )
                        launches[-1] = launches[-1].model_copy(
                            update={
                                "valid": batch_failure is None,
                                "failure": batch_failure,
                            }
                        )
                        self._write_report(
                            self._report(
                                smoke, batches, launches, gateway, batch_failure
                            )
                        )
                        if batch_failure is not None:
                            if execution.post_meter_error is not None:
                                raise execution.post_meter_error
                            raise HarborRunError(
                                f"Harbor batch {task_name} invalid: {batch_failure}"
                            )
                except (BudgetExceededError, CreditMeterError, HarborRunError) as error:
                    failure = str(error)
                    self._write_report(
                        self._report(smoke, batches, launches, gateway, failure)
                    )
                    raise
        finally:
            if self._owned_credit_meter is not None:
                await self._owned_credit_meter.aclose()
        return self._report(smoke, batches, launches, gateway, failure)

    async def _resolve_fingerprints(
        self, task_name: str
    ) -> tuple[TrialFingerprint, ...]:
        git_revision = await self._capture(("git", "rev-parse", "HEAD"), "git revision")
        image_id = await self._capture(
            ("docker", "image", "inspect", "--format", "{{.Id}}", "workbench:dev"),
            "workbench:dev image ID",
        )
        inputs = hash_harbor_inputs(self.config.tasks_root / task_name)
        return build_trial_fingerprints(
            git_revision=git_revision,
            image_id=image_id,
            task_name=task_name,
            task_source_sha256=inputs.task_source_sha256,
            environment_sha256=inputs.environment_sha256,
        )

    async def _execute_launch(
        self,
        *,
        gateway: ProviderGateway,
        credits: CreditSnapshot,
        forecast: float,
        task_name: str,
        attempts: int,
        phase: Literal["smoke", "additional", "matrix"],
        job_label: str | None,
        sequence: int,
    ) -> LaunchExecution:
        self._budget.assert_can_launch(credits, projected_worst_case_usd=forecast)
        start_sequence = gateway.provenance[-1].sequence if gateway.provenance else 0
        command = build_harbor_command(
            self.config,
            task_name,
            gateway_port=gateway.port,
            gateway_token=self._gateway_token.get_secret_value(),
            attempts=attempts,
            job_label=job_label,
        )
        completed = await self._commands.run(command, cwd=self.config.repository)
        after = await self._credit_meter.query()
        post_meter_error: BudgetExceededError | CreditMeterError | None = None
        try:
            metered_cost = self._budget.metered_cost(credits, after)
            self._budget.assert_observed_within_cap(after)
        except (BudgetExceededError, CreditMeterError) as error:
            post_meter_error = error
            metered_cost = max(0.0, float(after.total_usage - credits.total_usage))
        job_name = command[command.index("--job-name") + 1]
        outcomes = load_trial_outcomes(self.config.jobs_dir / job_name)
        end_sequence = (
            gateway.provenance[-1].sequence if gateway.provenance else start_sequence
        )
        launch = LaunchReport(
            sequence=sequence,
            phase=phase,
            task_name=task_name,
            job_name=job_name,
            attempts_per_model=attempts,
            enforced_model_routes={
                alias: MODEL_PROVIDERS[full_model]
                for alias, full_model in ALIAS_TO_MODEL.items()
            },
            gateway_sequences=GatewaySequenceSpan(
                start_exclusive=start_sequence,
                end_inclusive=end_sequence,
            ),
            usage_before=float(credits.total_usage),
            usage_after=float(after.total_usage),
            metered_cost_usd=metered_cost,
            projected_worst_case_usd=forecast,
            valid=False,
        )
        return LaunchExecution(
            launch=launch,
            outcomes=outcomes,
            completed=completed,
            credits_after=after,
            post_meter_error=post_meter_error,
        )

    def _report(
        self,
        smoke: SmokeReport | None,
        batches: list[BatchReport],
        launches: list[LaunchReport],
        gateway: ProviderGateway,
        failure: str | None,
    ) -> MatrixReport:
        return MatrixReport(
            run_id=self.config.run_id,
            baseline_usage=float(self._budget.baseline_usage),
            cap_usage=self._budget.cap_usage,
            smoke=smoke,
            batches=tuple(batches),
            launches=tuple(launches),
            gateway_provenance=tuple(gateway.provenance),
            failure=failure,
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


class LaunchExecution(BaseModel):
    launch: LaunchReport
    outcomes: tuple[TrialOutcome, ...]
    completed: CompletedCommand
    credits_after: CreditSnapshot
    post_meter_error: BudgetExceededError | CreditMeterError | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _launch_failure(execution: LaunchExecution) -> str | None:
    if execution.post_meter_error is not None:
        return str(execution.post_meter_error)
    if execution.completed.returncode != 0:
        return (
            f"Harbor batch {execution.launch.task_name} exited "
            f"{execution.completed.returncode}"
        )
    return None


def _build_trial_records(
    outcomes: tuple[TrialOutcome, ...],
    fingerprints: tuple[TrialFingerprint, ...],
    *,
    job_name: str,
    phase: Literal["smoke", "additional", "matrix"],
    first_attempt: int,
) -> tuple[TrialRecord, ...]:
    by_alias = {
        alias: next(
            fingerprint
            for fingerprint in fingerprints
            if fingerprint.model == ALIAS_TO_MODEL[alias]
        )
        for alias in MODEL_ALIASES
    }
    seen: Counter[str | None] = Counter()
    records: list[TrialRecord] = []
    for outcome in outcomes:
        alias = outcome.model_alias
        attempt: int | None = None
        fingerprint: TrialFingerprint | None = None
        if alias in by_alias:
            attempt = first_attempt + seen[alias]
            fingerprint = by_alias[alias]
        seen[alias] += 1
        records.append(
            TrialRecord(
                attempt=attempt,
                source_job_name=job_name,
                phase=phase,
                fingerprint=fingerprint,
                outcome=outcome,
            )
        )
    return tuple(records)


def _fingerprint_sets_reusable(
    smoke: tuple[TrialFingerprint, ...],
    final: tuple[TrialFingerprint, ...],
    *,
    smoke_valid: bool,
) -> bool:
    return len(smoke) == len(final) and all(
        smoke_is_reusable(smoke_item, final_item, smoke_valid=smoke_valid)
        for smoke_item, final_item in zip(smoke, final, strict=True)
    )


def _exception_name(exception_info: object) -> str:
    if isinstance(exception_info, dict):
        for key in ("exception_type", "type", "name"):
            value = exception_info.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(exception_info, str) and exception_info:
        return exception_info
    return "trial exception"

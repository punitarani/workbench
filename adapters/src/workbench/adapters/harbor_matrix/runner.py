import asyncio
import hashlib
import logging
import math
import os
import re
import signal
import stat
import tempfile
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Literal, Protocol, Self

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
    field_validator,
    model_validator,
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
from workbench.adapters.harbor_matrix.provenance import (
    collect_run_provenance,
    write_run_provenance,
)
from workbench.adapters.harness.openrouter_client import MODEL_PROVIDERS

LOGGER = logging.getLogger(__name__)
# Where the tracked per-cell summaries land; jobs/ is gitignored and may be
# disposable, so the evidence a paid batch bought lives here instead.
DOCS_RUN_NAME = "2026-08-09-four-month-history"
HARBOR_VERSION = "0.18.0"
CODEX_VERSION = "0.147.0"
HARTWELL_CODEX_IMPORT_PATH = (
    "workbench.adapters.harbor_matrix.codex_agent:HartwellCodex"
)
CODEX_COMPACTION_MODE: Literal["custom-provider-local"] = "custom-provider-local"
AGENT_TIMEOUT_MULTIPLIER = 2.0
# Per-key, not org-wide. /credits reports the whole account, so on a pooled
# key another team's traffic lands in this run's metered cost: a nine-task
# batch aborted on every task with "$26.10 observed versus $20.00 authorized"
# while its own spend was $1.23 a task. /key bills only this credential.
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/key"
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
    "settlement-authority-audit",
)
TaskName = Literal[
    "fee-dispute-reconstruction",
    "client-departure-postmortem",
    "billing-hygiene-audit",
    "second-read-audit",
    "visitor-log-audit",
    "operative-deadline",
    "standard-drift",
    "vanished-clause",
    "settlement-authority-audit",
]
TrialPhase = Literal["smoke", "diagnostic-smoke", "additional", "matrix"]
IGNORED_TASK_SOURCE_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "bundle",
    "environment",
    "jobs",
}


class DisposableJobsDirError(ValueError):
    """A batch would write paid trial artifacts into a removable worktree."""


class MatrixConfig(BaseModel):
    repository: Path
    tasks_root: Path
    jobs_dir: Path
    # True when jobs_dir was derived from ``repository`` rather than passed
    # explicitly. A derived directory inside a worktree is refused: every
    # trial artifact lives under jobs_dir, removing the worktree destroys
    # them, and a settled batch cannot be re-run to recover what it paid for.
    jobs_dir_is_derived: bool = False
    run_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    tasks: tuple[TaskName, ...] = Field(default=TASK_ORDER, min_length=1)
    attempts: Literal[3] = 3
    diagnostic_smoke: bool = False
    diagnostic_models: tuple[str, ...] | None = None
    concurrency: int = Field(default=8, ge=1, le=8)
    projected_worst_case_batch_usd: FiniteFloat = Field(gt=0)
    budget_baseline_usage: FiniteFloat = Field(default=32.2139, ge=0)
    project_cap_usd: FiniteFloat = Field(default=25.0, gt=0)
    credit_poll_interval_sec: FiniteFloat = Field(default=30.0, gt=0)
    gateway_bind_host: str = "0.0.0.0"

    @model_validator(mode="after")
    def durable_jobs_dir(self) -> MatrixConfig:
        """Refuse a *derived* jobs_dir that resolves under a worktree.

        Deriving it from ``repository`` once put roughly $34 of settled
        diagnostics — 47 cells of result.json, reward-details.json, and
        trajectory.json — inside a git worktree that was later removed,
        destroying all of it. An explicit ``--jobs-dir`` is an informed
        choice and is always honoured; a derived one must be durable.
        """

        if not self.jobs_dir_is_derived:
            return self
        parts = {part.lower() for part in self.jobs_dir.resolve().parts}
        if parts & {"worktrees", ".git"}:
            raise DisposableJobsDirError(
                f"refusing to derive jobs_dir from a disposable path: "
                f"{self.jobs_dir}. Trial artifacts would be destroyed with the "
                f"worktree; pass --jobs-dir explicitly to a durable location."
            )
        return self

    @field_validator("tasks")
    @classmethod
    def canonical_tasks(cls, tasks: tuple[TaskName, ...]) -> tuple[TaskName, ...]:
        if len(set(tasks)) != len(tasks):
            raise ValueError("tasks must not contain duplicates")
        selected = set(tasks)
        return tuple(task for task in TASK_ORDER if task in selected)

    @field_validator("diagnostic_models")
    @classmethod
    def canonical_diagnostic_models(
        cls, models: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if models is None:
            return None
        if not models:
            raise ValueError("diagnostic_models must not be empty")
        if len(set(models)) != len(models):
            raise ValueError("diagnostic_models must not contain duplicates")
        unsupported = set(models) - set(MODEL_ALIASES)
        if unsupported:
            raise ValueError(f"unsupported diagnostic_models: {sorted(unsupported)}")
        selected = set(models)
        return tuple(alias for alias in MODEL_ALIASES if alias in selected)

    @model_validator(mode="after")
    def diagnostic_smoke_has_one_task(self) -> Self:
        if self.diagnostic_smoke and len(self.tasks) != 1:
            raise ValueError("diagnostic_smoke requires exactly one selected task")
        if self.diagnostic_smoke and self.diagnostic_models is None:
            self.diagnostic_models = MODEL_ALIASES
        if not self.diagnostic_smoke and self.diagnostic_models is not None:
            raise ValueError("diagnostic_models requires diagnostic_smoke")
        return self


class CreditSnapshot(BaseModel):
    # /key reports this credential's lifetime spend as "usage" and states no
    # grant total; a pooled key's org grant is not a budget this run owns, so
    # total_credits carries no meaning here and only the delta is used.
    total_usage: FiniteFloat = Field(ge=0, alias="usage")
    total_credits: FiniteFloat = Field(default=0.0, ge=0)

    model_config = ConfigDict(populate_by_name=True)


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

    def assert_in_flight_authorized(
        self,
        before: CreditSnapshot,
        observed: CreditSnapshot,
        *,
        authorized_cost_usd: float,
    ) -> None:
        cost = self.metered_cost(before, observed)
        if observed.total_usage + self.reserve_usd > self.cap_usage:
            raise BudgetExceededError(
                "observed in-flight usage consumed the Hartwell reserve: "
                f"${observed.total_usage:.4f} used versus "
                f"${self.cap_usage - self.reserve_usd:.4f} pre-reserve limit"
            )
        if cost > authorized_cost_usd:
            raise BudgetExceededError(
                "observed in-flight cost exceeded the authorized launch forecast: "
                f"${cost:.4f} observed versus ${authorized_cost_usd:.4f} authorized"
            )


def launch_projection(
    full_batch_projection_usd: float,
    *,
    attempts_per_model: int,
    model_count: int = len(MODEL_ALIASES),
) -> float:
    if not 1 <= attempts_per_model <= 3:
        raise ValueError("attempts_per_model must be between 1 and 3")
    if not 1 <= model_count <= len(MODEL_ALIASES):
        raise ValueError(f"model_count must be between 1 and {len(MODEL_ALIASES)}")
    return (
        full_batch_projection_usd
        * attempts_per_model
        * model_count
        / (3 * len(MODEL_ALIASES))
    )


def full_batch_projection_from_launch(
    launch_cost_usd: float,
    *,
    attempts_per_model: int,
    model_count: int = len(MODEL_ALIASES),
) -> float:
    if not 1 <= attempts_per_model <= 3:
        raise ValueError("attempts_per_model must be between 1 and 3")
    if not 1 <= model_count <= len(MODEL_ALIASES):
        raise ValueError(f"model_count must be between 1 and {len(MODEL_ALIASES)}")
    return launch_cost_usd * 3 * len(MODEL_ALIASES) / (attempts_per_model * model_count)


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
    codex_agent: str = HARTWELL_CODEX_IMPORT_PATH
    codex_compaction_mode: Literal["custom-provider-local"] = CODEX_COMPACTION_MODE
    agent_timeout_multiplier: float = AGENT_TIMEOUT_MULTIPLIER
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


class JobCleaner(Protocol):
    async def cleanup(self, job_dir: Path) -> None: ...


class NoopJobCleaner:
    async def cleanup(self, job_dir: Path) -> None:
        del job_dir


def _compose_projects_for_job(job_dir: Path) -> tuple[str, ...]:
    if not job_dir.is_dir():
        return ()
    projects = []
    for trial in sorted(job_dir.iterdir(), key=lambda path: path.name):
        metadata = trial.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            continue
        if not re.fullmatch(r"[A-Za-z0-9._-]+__[A-Za-z0-9]+", trial.name):
            continue
        projects.append(f"{trial.name.lower()}__env")
    return tuple(projects)


class DockerComposeJobCleaner:
    def __init__(self, commands: CommandRunner, repository: Path) -> None:
        self._commands = commands
        self._repository = repository

    async def cleanup(self, job_dir: Path) -> None:
        for project in _compose_projects_for_job(job_dir):
            await self._remove_project_resources("container", project)
            await self._remove_project_resources("network", project)

    async def _remove_project_resources(self, kind: str, project: str) -> None:
        listed = await self._commands.run(
            (
                "docker",
                kind,
                "ls",
                "-aq" if kind == "container" else "-q",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ),
            cwd=self._repository,
        )
        if listed.returncode != 0:
            raise HarborRunError(f"could not list Docker {kind}s for {project}")
        identifiers = tuple(listed.stdout.split())
        if not identifiers:
            return
        if not all(re.fullmatch(r"[0-9a-f]{12,64}", value) for value in identifiers):
            raise HarborRunError(f"Docker returned an invalid {kind} id for {project}")
        removal = ("docker", kind, "rm")
        if kind == "container":
            removal += ("-f",)
        removed = await self._commands.run(
            removal + identifiers,
            cwd=self._repository,
        )
        if removed.returncode != 0:
            raise HarborRunError(f"could not remove Docker {kind}s for {project}")


class CreditReader(Protocol):
    async def query(self) -> CreditSnapshot: ...


class SubprocessCommandRunner:
    async def run(self, command: tuple[str, ...], *, cwd: Path) -> CompletedCommand:
        environment = os.environ.copy()
        adapter_root = str(Path(__file__).resolve().parents[3])
        python_paths = [adapter_root]
        if existing_python_path := environment.get("PYTHONPATH"):
            python_paths.extend(existing_python_path.split(os.pathsep))
        environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_paths))
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            await _terminate_process_group(process)
            raise
        return CompletedCommand(
            returncode=process.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.communicate(), timeout=10.0)
    except TimeoutError:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.communicate()


class GatewaySequenceSpan(BaseModel):
    start_exclusive: int = Field(ge=0)
    end_inclusive: int = Field(ge=0)


class LaunchReport(BaseModel):
    sequence: int = Field(ge=1)
    phase: TrialPhase
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
    phase: TrialPhase
    fingerprint: TrialFingerprint | None
    outcome: TrialOutcome


class SmokeReport(BaseModel):
    task_name: TaskName
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
    gateway_env_file: Path,
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
        HARTWELL_CODEX_IMPORT_PATH,
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
            "--agent-timeout-multiplier",
            str(AGENT_TIMEOUT_MULTIPLIER),
            "--ak",
            f"version={CODEX_VERSION}",
            "--ak",
            f"compaction_mode={CODEX_COMPACTION_MODE}",
            "--ae",
            f"OPENAI_BASE_URL=http://host.docker.internal:{gateway_port}/v1",
            "--env-file",
            str(gateway_env_file),
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
    outcomes: tuple[TrialOutcome, ...],
    *,
    attempts: int,
    model_aliases: tuple[str, ...] = MODEL_ALIASES,
) -> None:
    invalid = [outcome for outcome in outcomes if not outcome.valid]
    if invalid:
        raise HarborRunError(f"Harbor batch has {len(invalid)} invalid trials")
    actual = Counter(outcome.model_alias for outcome in outcomes)
    if not model_aliases or len(set(model_aliases)) != len(model_aliases):
        raise HarborRunError("expected model aliases must be nonempty and unique")
    if set(model_aliases) - set(MODEL_ALIASES):
        raise HarborRunError("expected model aliases contain an unsupported alias")
    expected = Counter({alias: attempts for alias in model_aliases})
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
            codex_agent=HARTWELL_CODEX_IMPORT_PATH,
            codex_compaction_mode=CODEX_COMPACTION_MODE,
            agent_timeout_multiplier=AGENT_TIMEOUT_MULTIPLIER,
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
        job_cleaner: JobCleaner | None = None,
        credit_meter: CreditReader | None = None,
        gateway_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._git_revision: str | None = None
        self._openrouter_api_key = SecretStr(openrouter_api_key)
        self._gateway_token = SecretStr(gateway_token)
        self._commands = commands or SubprocessCommandRunner()
        self._job_cleaner = job_cleaner or (
            DockerComposeJobCleaner(self._commands, config.repository)
            if commands is None
            else NoopJobCleaner()
        )
        if credit_meter is None:
            self._owned_credit_meter: CreditMeter | None = CreditMeter(
                openrouter_api_key
            )
            self._credit_meter: CreditReader = self._owned_credit_meter
        else:
            self._owned_credit_meter = None
            self._credit_meter = credit_meter
        self._gateway_transport = gateway_transport
        self._budget = CreditBudget(
            baseline_usage=config.budget_baseline_usage,
            project_cap_usd=config.project_cap_usd,
        )

    async def run(self) -> MatrixReport:
        report_path = self._report_path()
        if report_path.exists() or report_path.is_symlink():
            raise HarborRunError(f"matrix report already exists: {report_path}")
        harbor_version = await self._commands.run(
            ("harbor", "--version"), cwd=self.config.repository
        )
        if harbor_version.returncode != 0:
            raise HarborRunError("could not read the Harbor version")
        validate_harbor_version(harbor_version.stdout)
        credits = await self._credit_meter.query()
        full_batch_forecast = float(self.config.projected_worst_case_batch_usd)
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
                    if self.config.diagnostic_smoke:
                        diagnostic_task = self.config.tasks[0]
                        diagnostic_models = self.config.diagnostic_models
                        if diagnostic_models is None:
                            raise HarborRunError(
                                "diagnostic smoke has no selected models"
                            )
                        diagnostic_fingerprints = await self._resolve_fingerprints(
                            diagnostic_task
                        )
                        diagnostic_execution = await self._execute_launch(
                            gateway=gateway,
                            credits=credits,
                            forecast=launch_projection(
                                full_batch_forecast,
                                attempts_per_model=1,
                                model_count=len(diagnostic_models),
                            ),
                            task_name=diagnostic_task,
                            attempts=1,
                            phase="diagnostic-smoke",
                            job_label="diagnostic-smoke",
                            sequence=1,
                            model_aliases=diagnostic_models,
                        )
                        launches.append(diagnostic_execution.launch)
                        diagnostic_trials = _build_trial_records(
                            diagnostic_execution.outcomes,
                            diagnostic_fingerprints,
                            job_name=diagnostic_execution.launch.job_name,
                            phase="diagnostic-smoke",
                            first_attempt=1,
                        )
                        diagnostic_failure = _launch_failure(diagnostic_execution)
                        if diagnostic_failure is None:
                            try:
                                validate_batch_outcomes(
                                    diagnostic_execution.outcomes,
                                    attempts=1,
                                    model_aliases=diagnostic_models,
                                )
                            except HarborRunError as error:
                                diagnostic_failure = (
                                    f"diagnostic smoke invalid: {error}"
                                )
                        smoke = SmokeReport(
                            task_name=diagnostic_task,
                            job_name=diagnostic_execution.launch.job_name,
                            valid=diagnostic_failure is None,
                            failure=diagnostic_failure,
                            trials=diagnostic_trials,
                            launch_sequence=1,
                        )
                        launches[-1] = launches[-1].model_copy(
                            update={
                                "valid": diagnostic_failure is None,
                                "failure": diagnostic_failure,
                            }
                        )
                        report = self._report(
                            smoke,
                            batches,
                            launches,
                            gateway,
                            diagnostic_failure,
                        )
                        self._write_report(report)
                        if diagnostic_failure is not None:
                            if diagnostic_execution.post_meter_error is not None:
                                raise diagnostic_execution.post_meter_error
                            raise HarborRunError(diagnostic_failure)
                        return report
                    fee_task = TASK_ORDER[0]
                    if fee_task not in self.config.tasks:
                        await self._execute_matrix_tasks(
                            gateway=gateway,
                            credits=credits,
                            full_batch_forecast=full_batch_forecast,
                            task_names=self.config.tasks,
                            start_sequence=1,
                            smoke=smoke,
                            batches=batches,
                            launches=launches,
                        )
                        return self._report(smoke, batches, launches, gateway, failure)
                    smoke_fingerprints = await self._resolve_fingerprints(fee_task)
                    smoke_execution = await self._execute_launch(
                        gateway=gateway,
                        credits=credits,
                        forecast=launch_projection(
                            full_batch_forecast, attempts_per_model=1
                        ),
                        task_name=fee_task,
                        attempts=1,
                        phase="smoke",
                        job_label="smoke",
                        sequence=1,
                    )
                    launches.append(smoke_execution.launch)
                    credits = smoke_execution.credits_after
                    full_batch_forecast = max(
                        full_batch_forecast,
                        full_batch_projection_from_launch(
                            smoke_execution.launch.metered_cost_usd,
                            attempts_per_model=1,
                        ),
                    )
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
                        forecast=launch_projection(
                            full_batch_forecast, attempts_per_model=2
                        ),
                        task_name=fee_task,
                        attempts=2,
                        phase="additional",
                        job_label="additional",
                        sequence=2,
                    )
                    launches.append(fee_execution.launch)
                    credits = fee_execution.credits_after
                    full_batch_forecast = max(
                        full_batch_forecast,
                        full_batch_projection_from_launch(
                            fee_execution.launch.metered_cost_usd,
                            attempts_per_model=2,
                        ),
                    )
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

                    await self._execute_matrix_tasks(
                        gateway=gateway,
                        credits=credits,
                        full_batch_forecast=full_batch_forecast,
                        task_names=tuple(
                            task for task in self.config.tasks if task != fee_task
                        ),
                        start_sequence=3,
                        smoke=smoke,
                        batches=batches,
                        launches=launches,
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

    async def _execute_matrix_tasks(
        self,
        *,
        gateway: ProviderGateway,
        credits: CreditSnapshot,
        full_batch_forecast: float,
        task_names: tuple[TaskName, ...],
        start_sequence: int,
        smoke: SmokeReport | None,
        batches: list[BatchReport],
        launches: list[LaunchReport],
    ) -> tuple[CreditSnapshot, float]:
        for sequence, task_name in enumerate(task_names, start=start_sequence):
            fingerprints = await self._resolve_fingerprints(task_name)
            execution = await self._execute_launch(
                gateway=gateway,
                credits=credits,
                forecast=launch_projection(full_batch_forecast, attempts_per_model=3),
                task_name=task_name,
                attempts=3,
                phase="matrix",
                job_label=None,
                sequence=sequence,
            )
            launches.append(execution.launch)
            credits = execution.credits_after
            full_batch_forecast = max(
                full_batch_forecast,
                full_batch_projection_from_launch(
                    execution.launch.metered_cost_usd,
                    attempts_per_model=3,
                ),
            )
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
                self._report(smoke, batches, launches, gateway, batch_failure)
            )
            if batch_failure is not None:
                if execution.post_meter_error is not None:
                    raise execution.post_meter_error
                raise HarborRunError(
                    f"Harbor batch {task_name} invalid: {batch_failure}"
                )
        return credits, full_batch_forecast

    async def _resolve_fingerprints(
        self, task_name: str
    ) -> tuple[TrialFingerprint, ...]:
        git_revision = await self._capture(("git", "rev-parse", "HEAD"), "git revision")
        # Remembered so the durable per-cell summary can stamp the revision
        # the batch actually ran, without re-shelling at report time.
        self._git_revision = git_revision
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
        phase: TrialPhase,
        job_label: str | None,
        sequence: int,
        model_aliases: tuple[str, ...] = MODEL_ALIASES,
    ) -> LaunchExecution:
        start_sequence = gateway.provenance[-1].sequence if gateway.provenance else 0
        gateway_env_file = _create_gateway_env_file(self._gateway_token)
        in_flight_error: BudgetExceededError | CreditMeterError | None = None
        try:
            command = build_harbor_command(
                self.config,
                task_name,
                gateway_port=gateway.port,
                gateway_env_file=gateway_env_file,
                attempts=attempts,
                model_aliases=model_aliases,
                job_label=job_label,
            )
            job_name = command[command.index("--job-name") + 1]
            job_dir = self.config.jobs_dir / job_name
            if job_dir.exists() or job_dir.is_symlink():
                raise HarborRunError(f"Harbor job directory already exists: {job_dir}")
            self._budget.assert_can_launch(credits, projected_worst_case_usd=forecast)
            try:
                completed = await self._run_with_budget_monitor(
                    command,
                    credits=credits,
                    forecast=forecast,
                )
            except (BudgetExceededError, CreditMeterError) as error:
                in_flight_error = error
                try:
                    await self._job_cleaner.cleanup(job_dir)
                except HarborRunError as cleanup_error:
                    in_flight_error.args = (
                        f"{in_flight_error}; Docker cleanup failed: {cleanup_error}",
                    )
                completed = CompletedCommand(returncode=1, stderr=str(error))
        finally:
            gateway_env_file.unlink(missing_ok=True)
        after = await self._credit_meter.query()
        post_meter_error = in_flight_error
        try:
            metered_cost = self._budget.metered_cost(credits, after)
            self._budget.assert_observed_within_cap(after)
        except (BudgetExceededError, CreditMeterError) as error:
            if post_meter_error is None:
                post_meter_error = error
            metered_cost = max(0.0, float(after.total_usage - credits.total_usage))
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
                if alias in model_aliases
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

    async def _run_with_budget_monitor(
        self,
        command: tuple[str, ...],
        *,
        credits: CreditSnapshot,
        forecast: float,
    ) -> CompletedCommand:
        running = asyncio.create_task(
            self._commands.run(command, cwd=self.config.repository)
        )
        try:
            while True:
                done, _ = await asyncio.wait(
                    {running},
                    timeout=float(self.config.credit_poll_interval_sec),
                )
                if done:
                    return await running
                observed = await self._credit_meter.query()
                self._budget.assert_in_flight_authorized(
                    credits,
                    observed,
                    authorized_cost_usd=forecast,
                )
        except BaseException:
            if not running.done():
                running.cancel()
                with suppress(asyncio.CancelledError):
                    await running
            raise

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
        self._report_path().write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        self._write_provenance()

    def _write_provenance(self) -> None:
        """Persist per-cell criteria and tool histograms where git keeps them.

        Best effort by design: a batch that produced real scores must not be
        reported as failed because a summary could not be written.
        """

        try:
            provenance = collect_run_provenance(
                self.config.jobs_dir,
                run_id=self.config.run_id,
                git_revision=self._git_revision,
            )
            write_run_provenance(provenance, self._docs_run_dir())
        except OSError as error:  # pragma: no cover - filesystem edge
            LOGGER.warning("could not write run provenance: %s", error)

    def _docs_run_dir(self) -> Path:
        return self.config.repository / "docs/runs" / DOCS_RUN_NAME

    def _report_path(self) -> Path:
        return self.config.jobs_dir / f"{self.config.run_id}-matrix.json"


class LaunchExecution(BaseModel):
    launch: LaunchReport
    outcomes: tuple[TrialOutcome, ...]
    completed: CompletedCommand
    credits_after: CreditSnapshot
    post_meter_error: BudgetExceededError | CreditMeterError | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _create_gateway_env_file(gateway_token: SecretStr) -> Path:
    token = gateway_token.get_secret_value()
    if "\n" in token or "\r" in token:
        raise ValueError("gateway token contains a newline")
    descriptor, raw_path = tempfile.mkstemp(prefix="hartwell-gateway-", suffix=".env")
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as env_file:
            descriptor = -1
            env_file.write(f"HARTWELL_GATEWAY_TOKEN={token}\n")
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        Path(raw_path).unlink(missing_ok=True)
        raise
    return Path(raw_path)


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
    phase: TrialPhase,
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

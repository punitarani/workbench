"""Durable per-cell provenance for a paid Harbor batch.

``jobs/`` is gitignored and, when the runner derives it from a worktree,
disposable: roughly $34 of settled diagnostics was destroyed with one
``git worktree remove``. The scalars survived in ``*-matrix.json``; what
could not be reconstructed were the per-criterion tables and the MCP
tool-call histograms, which are precisely what tells you *why* a model
scored what it did.

This module reads a finished job directory and writes a compact, tracked
summary under ``docs/runs/<run>/``. It is read-only over the job tree and
never fails a batch: a missing or malformed artifact yields a cell that
says so rather than raising.
"""

import json
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# Codex reaches MCP tools either as a function call named
# ``mcp__<server>__<tool>`` or, under unified_exec, as ``tools.mcp__…()``
# inside a JavaScript blob. Counting the identifier itself catches both.
_MCP_CALL = re.compile(r"mcp__([A-Za-z0-9_]+?)__([A-Za-z0-9_]+)")


class CriterionScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    name: str
    value: float
    weight: float
    reasoning: str | None = None
    error: str | None = None


class CellSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_name: str
    run_id: str
    git_revision: str | None = None
    trial_name: str | None = None
    model_alias: str | None = None
    attempt: int | None = None
    valid: bool = False
    reason: str | None = None
    reward: float | None = None
    answer: float | None = None
    process: float | None = None
    criteria: tuple[CriterionScore, ...] = ()
    tool_calls: dict[str, int] = {}
    tool_call_total: int = 0
    wall_time_sec: float | None = None
    stop_reason: str | None = None
    artifacts_missing: tuple[str, ...] = ()


class RunProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    git_revision: str | None = None
    source_jobs_dir: str
    cells: tuple[CellSummary, ...] = ()


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None


def read_criteria(reward_details: Path) -> tuple[CriterionScore, ...]:
    """Flatten Reward Kit's per-dimension breakdown into one table."""

    payload = _read_json(reward_details)
    if not isinstance(payload, dict):
        return ()
    scores: list[CriterionScore] = []
    for dimension, detail in payload.items():
        entries = detail if isinstance(detail, list) else [detail]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for criterion in entry.get("criteria") or ():
                if not isinstance(criterion, dict):
                    continue
                try:
                    scores.append(
                        CriterionScore(
                            dimension=str(dimension),
                            name=str(criterion.get("name", "")),
                            value=float(criterion.get("value", 0.0)),
                            weight=float(criterion.get("weight", 0.0)),
                            reasoning=criterion.get("reasoning"),
                            error=criterion.get("error"),
                        )
                    )
                except TypeError, ValueError:
                    continue
    return tuple(scores)


def read_tool_calls(agent_log: Path) -> Counter[str]:
    """Histogram of ``server.tool`` MCP invocations in the agent log."""

    try:
        text = agent_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return Counter()
    return Counter(f"{server}.{tool}" for server, tool in _MCP_CALL.findall(text))


def summarize_trial(
    trial_dir: Path, *, task_name: str, run_id: str, git_revision: str | None
) -> CellSummary:
    missing: list[str] = []
    result = _read_json(trial_dir / "result.json")
    if result is None:
        missing.append("result.json")
    result = result if isinstance(result, dict) else {}

    rewards = ((result.get("verifier_result") or {}).get("rewards")) or {}
    config = result.get("config") or {}
    agent = config.get("agent") if isinstance(config, dict) else None

    details = trial_dir / "verifier" / "reward-details.json"
    if not details.is_file():
        missing.append("verifier/reward-details.json")
    criteria = read_criteria(details)

    agent_log = trial_dir / "agent" / "codex.txt"
    if not agent_log.is_file():
        missing.append("agent/codex.txt")
    histogram = read_tool_calls(agent_log)

    def number(key: str) -> float | None:
        value = rewards.get(key) if isinstance(rewards, dict) else None
        return float(value) if isinstance(value, (int, float)) else None

    exception = result.get("exception_info")
    return CellSummary(
        task_name=task_name,
        run_id=run_id,
        git_revision=git_revision,
        trial_name=result.get("trial_name") or trial_dir.name,
        model_alias=(
            (agent or {}).get("model_name") if isinstance(agent, dict) else None
        ),
        attempt=(
            result.get("attempt") if isinstance(result.get("attempt"), int) else None
        ),
        valid=exception is None and bool(rewards),
        reason=None if exception is None else str(exception)[:500],
        reward=number("reward"),
        answer=number("answer"),
        process=number("process"),
        criteria=criteria,
        tool_calls=dict(sorted(histogram.items())),
        tool_call_total=sum(histogram.values()),
        wall_time_sec=(
            float(result["wall_time_sec"])
            if isinstance(result.get("wall_time_sec"), (int, float))
            else None
        ),
        stop_reason=result.get("stop_reason"),
        artifacts_missing=tuple(missing),
    )


def collect_run_provenance(
    jobs_dir: Path, *, run_id: str, git_revision: str | None = None
) -> RunProvenance:
    """Summarize every trial this run wrote under ``jobs_dir``."""

    cells: list[CellSummary] = []
    if jobs_dir.is_dir():
        for job_dir in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
            if run_id not in job_dir.name:
                continue
            # Job names are "<run-id>-<task>"; recover the task half.
            task_name = job_dir.name.split(run_id, 1)[-1].strip("-") or job_dir.name
            for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
                cells.append(
                    summarize_trial(
                        trial_dir,
                        task_name=task_name,
                        run_id=run_id,
                        git_revision=git_revision,
                    )
                )
    return RunProvenance(
        run_id=run_id,
        git_revision=git_revision,
        source_jobs_dir=str(jobs_dir),
        cells=tuple(cells),
    )


def write_run_provenance(provenance: RunProvenance, docs_run_dir: Path) -> Path:
    """Persist the summary where git tracks it, unlike ``jobs/``."""

    docs_run_dir.mkdir(parents=True, exist_ok=True)
    path = docs_run_dir / f"{provenance.run_id}-cells.json"
    path.write_text(provenance.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path

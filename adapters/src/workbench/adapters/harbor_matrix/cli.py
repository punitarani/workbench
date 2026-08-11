import argparse
import asyncio
import os
import secrets
from pathlib import Path

from workbench.adapters.harbor_matrix.runner import (
    TASK_ORDER,
    MatrixConfig,
    MatrixRunner,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m workbench.adapters.harbor_matrix",
        description="Run the provider-pinned Hartwell Harbor matrix.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--projected-worst-case-batch-usd",
        required=True,
        type=float,
        help="Conservative cost projection for a full nine-cell task batch.",
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--tasks-root", type=Path)
    parser.add_argument("--jobs-dir", type=Path)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--diagnostic-smoke",
        action="store_true",
        help="Run one non-reusable attempt per model for exactly one task.",
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--task", action="append", choices=TASK_ORDER)
    parser.add_argument("--budget-baseline-usage", type=float, default=32.2139)
    parser.add_argument("--project-cap-usd", type=float, default=25.0)
    parser.add_argument("--credit-poll-interval-sec", type=float, default=30.0)
    parser.add_argument("--gateway-bind-host", default="0.0.0.0")
    return parser


def parse_args(argv: list[str] | None = None) -> MatrixConfig:
    args = _parser().parse_args(argv)
    repository = args.repository.resolve()
    tasks_root = args.tasks_root or repository / "datasets/hartwell/tasks"
    jobs_dir = args.jobs_dir or repository / "jobs"
    selected = set(args.task or TASK_ORDER)
    return MatrixConfig(
        repository=repository,
        tasks_root=tasks_root,
        jobs_dir=jobs_dir,
        run_id=args.run_id,
        tasks=tuple(task for task in TASK_ORDER if task in selected),
        attempts=args.attempts,
        diagnostic_smoke=args.diagnostic_smoke,
        concurrency=args.concurrency,
        projected_worst_case_batch_usd=args.projected_worst_case_batch_usd,
        budget_baseline_usage=args.budget_baseline_usage,
        project_cap_usd=args.project_cap_usd,
        credit_poll_interval_sec=args.credit_poll_interval_sec,
        gateway_bind_host=args.gateway_bind_host,
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        _parser().error("OPENROUTER_API_KEY is not set")
    runner = MatrixRunner(
        config,
        openrouter_api_key=api_key,
        gateway_token=secrets.token_urlsafe(32),
    )
    report = asyncio.run(runner.run())
    report_path = config.jobs_dir / f"{config.run_id}-matrix.json"
    print(f"completed {len(report.batches)} task batches; report: {report_path}")
    return 0

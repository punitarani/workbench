"""Run the GEPA loop live against OpenRouter.

    uv run --env-file .env python -m simulation.optimize.cli \
        --generations 2 --children 3 --seeds 101,202 --max-calls 1200

The call cap is a hard ceiling shared by rollouts and reflection; on
exhaustion the loop returns the best candidate found so far. Results land
in out/gepa/ as JSON alongside every rollout's world log.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from simulation.lm.budget import BudgetedLM
from simulation.lm.openrouter import DEFAULT_MODEL, OpenRouterLM
from simulation.optimize.instructions import (
    InstructionSet,
    current_instructions,
)
from simulation.optimize.loop import optimize
from simulation.optimize.scenario import (
    BANNED_INSTRUCTION_TERMS,
    optimization_spec,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--children", type=int, default=3)
    parser.add_argument("--seeds", default="101,202")
    parser.add_argument("--max-calls", type=int, default=1200)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=Path("out/gepa"))
    parser.add_argument(
        "--from-results",
        type=Path,
        default=None,
        help="resume from a prior run's results.json, starting at its best",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required (uv run --env-file .env)")

    base = current_instructions()
    if args.from_results is not None:
        prior = json.loads(args.from_results.read_text())
        base = InstructionSet.model_validate(prior["best"]["instructions"])

    seeds = tuple(int(part) for part in args.seeds.split(","))
    budgeted = BudgetedLM(OpenRouterLM(api_key=api_key), max_calls=args.max_calls)

    result = asyncio.run(
        optimize(
            spec=optimization_spec(),
            base=base,
            seeds=seeds,
            generations=args.generations,
            children=args.children,
            inner_lm=budgeted,
            reflect_lm=budgeted,
            model=args.model,
            out_root=args.out,
            banned_terms=BANNED_INSTRUCTION_TERMS,
        )
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(result.model_dump_json(indent=2) + "\n")

    for candidate in result.history:
        marker = " <- best" if candidate.name == result.best.name else ""
        print(f"{candidate.name:12} mean={candidate.mean:.3f}{marker}")
        for card in candidate.cards:
            parts = ", ".join(f"{k}={v:.2f}" for k, v in card.components.items())
            print(f"    [{card.total:.3f}] {parts}")
    if result.budget_exhausted:
        print("budget exhausted — partial result")
    usage = budgeted.usage
    print(
        f"usage: {usage.prompt_tokens} prompt + {usage.completion_tokens} "
        f"completion tokens"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

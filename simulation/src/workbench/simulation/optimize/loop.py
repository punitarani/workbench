"""The reflective evolution loop.

One generation: take the best candidate, turn its scorecard misses into a
reflection prompt, ask the reflection model for revised ``decide``
instructions, evaluate every child on the same seeds, keep the winner.
dspy.GEPA optimizes per-call examples; this loop optimizes the day-level
behavior the audits actually measure. Rollouts that fail score zero with
the failure recorded — never silently dropped. A shared budgeted LM makes
cost overrun impossible: the loop stops with partial results instead.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events
from workbench.simulation.errors import LMBudgetExceededError
from workbench.simulation.lm.protocol import ChatMessage, LanguageModel, LMRequest
from workbench.simulation.optimize.instructions import InstructionSet, build_actor
from workbench.simulation.optimize.scenario import ScoreCard, score_day
from workbench.simulation.run import run_workplace
from workbench.simulation.workplace.spec import WorkplaceSpec


class CandidateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    instructions: InstructionSet
    cards: tuple[ScoreCard, ...]

    @property
    def mean(self) -> float:
        return round(sum(card.total for card in self.cards) / len(self.cards), 4)

    def findings(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for card in self.cards:
            for finding in card.findings:
                seen.setdefault(finding)
        return tuple(seen)


class OptimizationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    history: tuple[CandidateResult, ...]
    best: CandidateResult
    budget_exhausted: bool = False


async def evaluate(
    name: str,
    instructions: InstructionSet,
    *,
    spec: WorkplaceSpec,
    seeds: tuple[int, ...],
    inner_lm: LanguageModel,
    model: str,
    out_root: Path,
) -> CandidateResult:
    async def one(seed: int) -> ScoreCard:
        out_dir = out_root / f"{name}-seed{seed}"
        try:
            async with asyncio.timeout(900):
                await run_workplace(
                    spec,
                    seed=Seed(root=seed),
                    out_dir=out_dir,
                    inner_lm=inner_lm,
                    model=model,
                    actor_factory=lambda: build_actor(instructions),
                )
        except LMBudgetExceededError:
            raise
        except Exception as error:
            return ScoreCard(components={}, findings=(f"rollout failed: {error}",))
        return score_day(read_events(out_dir / "world.jsonl"))

    cards = await asyncio.gather(*(one(seed) for seed in seeds))
    return CandidateResult(name=name, instructions=instructions, cards=tuple(cards))


_REFLECTION_PROMPT = """\
You are optimizing the operating instructions for a simulated professional
persona in a workplace simulation. The persona follows the instruction below
when deciding its next action each time it checks in during the day.

Current instruction:
---
{current}
---

Across evaluation days it scored {mean:.2f} out of 1.00. Specific misses:
{findings}

Rewrite the instruction to fix these specific misses while keeping its
existing strengths (no invented work, no acknowledgment-only messages, no
redone work). Keep it under 220 words, imperative voice, plain prose.
Variant {variant}: emphasize a different aspect of the fixes than other
variants would. Reply with the revised instruction text only — no preamble,
no quotes, no markup."""


async def propose(
    parent: CandidateResult,
    *,
    reflect_lm: LanguageModel,
    model: str,
    children: int,
    seed_base: int,
) -> list[InstructionSet]:
    findings = "\n".join(f"- {finding}" for finding in parent.findings()) or "- none"
    current = parent.instructions.decide or ""

    async def one(variant: int) -> InstructionSet | None:
        prompt = _REFLECTION_PROMPT.format(
            current=current, mean=parent.mean, findings=findings, variant=variant
        )
        response = await reflect_lm.complete(
            LMRequest(
                model=model,
                messages=(ChatMessage(role="user", content=prompt),),
                max_tokens=800,
                temperature=1.0,
                seed=seed_base + variant,
                rollout_id=variant,
            )
        )
        text = response.text.strip()
        if len(text) < 80:
            return None
        return parent.instructions.model_copy(update={"decide": text})

    proposals = await asyncio.gather(*(one(i) for i in range(1, children + 1)))
    return [proposal for proposal in proposals if proposal is not None]


async def optimize(
    *,
    spec: WorkplaceSpec,
    base: InstructionSet,
    seeds: tuple[int, ...],
    generations: int,
    children: int,
    inner_lm: LanguageModel,
    reflect_lm: LanguageModel,
    model: str,
    out_root: Path,
) -> OptimizationResult:
    history: list[CandidateResult] = []
    try:
        best = await evaluate(
            "gen0-base",
            base,
            spec=spec,
            seeds=seeds,
            inner_lm=inner_lm,
            model=model,
            out_root=out_root,
        )
        history.append(best)
        for generation in range(1, generations + 1):
            candidates = await propose(
                best,
                reflect_lm=reflect_lm,
                model=model,
                children=children,
                seed_base=generation * 1000,
            )
            results = await asyncio.gather(
                *(
                    evaluate(
                        f"gen{generation}-c{index}",
                        candidate,
                        spec=spec,
                        seeds=seeds,
                        inner_lm=inner_lm,
                        model=model,
                        out_root=out_root,
                    )
                    for index, candidate in enumerate(candidates, start=1)
                )
            )
            history.extend(results)
            for result in results:
                if result.mean > best.mean:
                    best = result
    except LMBudgetExceededError:
        if not history:
            raise
        best = max(history, key=lambda result: result.mean)
        return OptimizationResult(
            history=tuple(history), best=best, budget_exhausted=True
        )
    return OptimizationResult(history=tuple(history), best=best)

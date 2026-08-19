"""The GEPA loop's plumbing, entirely offline: instruction application,
mechanical scoring, reflective proposal, and a full generation on fakes."""

from pathlib import Path

from simulation.lm.protocol import LMRequest, LMResponse, TokenUsage
from simulation.optimize.instructions import (
    InstructionSet,
    build_actor,
    current_instructions,
)
from simulation.optimize.loop import evaluate, optimize, propose
from simulation.optimize.scenario import (
    WEIGHTS,
    optimization_spec,
    score_day,
)
from simulation.persona.programs import DecideNextAction

DECIDE_IDLE = (
    "[[ ## choice ## ]]\n"
    '{"action": "idle", "target_ref": null, '
    '"intent": "Nothing pending", "reason": "Quiet"}\n\n'
    "[[ ## completed ## ]]"
)

NEW_INSTRUCTION = (
    "Choose the single most appropriate next action. Post requested status "
    "updates in chat, reply substantively to external questions with a "
    "stated turnaround, and idle when nothing needs you."
)


class ScriptLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        self.calls += 1
        return LMResponse(
            text=self._text,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
        )


def test_build_actor_applies_instructions_without_touching_the_class() -> None:
    shipped = DecideNextAction.instructions
    actor = build_actor(InstructionSet(decide="Do the right thing at work."))
    assert actor.decide.signature.instructions == "Do the right thing at work."
    assert DecideNextAction.instructions == shipped
    assert build_actor(InstructionSet()).decide.signature.instructions == shipped
    assert current_instructions().decide == shipped


async def test_idle_day_scores_discipline_only(tmp_path: Path) -> None:
    result = await evaluate(
        "idle",
        current_instructions(),
        spec=optimization_spec(),
        seeds=(7,),
        inner_lm=ScriptLM(DECIDE_IDLE),
        model="test/model",
        out_root=tmp_path,
    )
    [card] = result.cards
    assert card.total == WEIGHTS["channel_discipline"]
    assert card.components["chat_status"] == 0.0
    assert any("chat channel" in finding for finding in card.findings)
    assert result.mean == card.total


def test_score_day_gates_on_validation() -> None:
    card = score_day([])
    assert card.total == 0.0
    assert "validation" in card.findings[0]


async def test_propose_rewrites_decide_only() -> None:
    base = await _idle_result()
    reflect = ScriptLM(NEW_INSTRUCTION)
    [child] = await propose(
        base, reflect_lm=reflect, model="m", children=1, seed_base=0
    )
    assert child.decide == NEW_INSTRUCTION
    assert child.draft_email == base.instructions.draft_email
    short = ScriptLM("no.")
    assert (
        await propose(base, reflect_lm=short, model="m", children=2, seed_base=0) == []
    )


async def test_optimize_runs_a_generation_offline(tmp_path: Path) -> None:
    result = await optimize(
        spec=optimization_spec(),
        base=current_instructions(),
        seeds=(7,),
        generations=1,
        children=2,
        inner_lm=ScriptLM(DECIDE_IDLE),
        reflect_lm=ScriptLM(NEW_INSTRUCTION),
        model="test/model",
        out_root=tmp_path,
    )
    assert len(result.history) == 3, "baseline plus two children"
    assert result.best.name == "gen0-base", "idle children cannot beat the tie"
    assert not result.budget_exhausted


async def _idle_result():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        return await evaluate(
            "base",
            current_instructions(),
            spec=optimization_spec(),
            seeds=(7,),
            inner_lm=ScriptLM(DECIDE_IDLE),
            model="test/model",
            out_root=Path(tmp),
        )


async def test_propose_rejects_scenario_specific_text() -> None:
    base = await _idle_result()
    leaky = ScriptLM(
        "Post the forty-five day correction to the draft before any status. "
        "Verify the change exists in the repository; never claim completion "
        "without checking. Idle when nothing needs you."
    )
    rejected = await propose(
        base,
        reflect_lm=leaky,
        model="m",
        children=2,
        seed_base=0,
        banned_terms=("forty-five",),
    )
    assert rejected == [], "instructions quoting the evaluation day are invalid"

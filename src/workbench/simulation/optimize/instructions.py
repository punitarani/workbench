"""Candidate instruction sets: the GEPA-mutable surface.

Instructions are applied by constructing fresh predictors over
``Signature.with_instructions``, never by mutating the shared signature
classes — concurrent rollouts of different candidates must not interfere.
"""

import dspy
from pydantic import BaseModel, ConfigDict

from workbench.simulation.persona.programs import (
    DecideNextAction,
    DraftChatMessage,
    DraftEmail,
    ProfessionalActor,
)


class InstructionSet(BaseModel):
    """Overrides for the optimizable predictors; None keeps the shipped text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decide: str | None = None
    draft_email: str | None = None
    draft_chat: str | None = None


def current_instructions() -> InstructionSet:
    """The instructions as shipped, read from the signature docstrings."""
    return InstructionSet(
        decide=DecideNextAction.instructions,
        draft_email=DraftEmail.instructions,
        draft_chat=DraftChatMessage.instructions,
    )


def build_actor(instructions: InstructionSet) -> ProfessionalActor:
    actor = ProfessionalActor()
    if instructions.decide is not None:
        actor.decide = dspy.Predict(
            DecideNextAction.with_instructions(instructions.decide)
        )
    if instructions.draft_email is not None:
        actor.draft_email = dspy.Predict(
            DraftEmail.with_instructions(instructions.draft_email)
        )
    if instructions.draft_chat is not None:
        actor.draft_chat = dspy.Predict(
            DraftChatMessage.with_instructions(instructions.draft_chat)
        )
    return actor

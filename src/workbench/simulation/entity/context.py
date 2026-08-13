"""Structured context blocks and the single point where they become prompt text."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class ContextBlock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    content: str
    # Kept in transcripts for debugging; never rendered into model-visible text.
    debug_only: bool = False


def render_prompt(blocks: Sequence[ContextBlock]) -> str:
    visible = [b for b in blocks if not b.debug_only and b.content]
    return "\n\n".join(f"## {b.label}\n{b.content}" for b in visible)

"""Agent cognition events: reflections, summaries, and daily plans.

Offstage ``sim.*`` kinds — never materialized into product surfaces —
but first-class world events, so the log records *why* an agent acted,
snapshots stay id-only, and replay reproduces cognition byte for byte.
"""

from typing import Literal

from pydantic import Field

from workbench.core.events._base import Payload
from workbench.core.ids import EntityName


class MemoryBullet(Payload):
    text: str
    importance: int = Field(ge=1, le=10)
    # Typed world refs this thought is about (thr-/tkt-/cnv-/doc-/...).
    refs: tuple[str, ...] = ()


class PlanBlock(Payload):
    # Seconds since the day's midnight; blocks are clamped by the GM to
    # the working day and must not overlap.
    start: int = Field(ge=0, lt=86_400)
    end: int = Field(gt=0, le=86_400)
    focus: str
    refs: tuple[str, ...] = ()


class SimAgentMemoryPayload(Payload):
    kind: Literal["sim.agent.memory"]
    note_id: str
    entity: EntityName
    note_kind: Literal["daily_summary", "weekly_summary", "note"]
    day: str
    bullets: tuple[MemoryBullet, ...] = Field(min_length=1)
    open_loops: tuple[str, ...] = ()


class SimAgentPlanPayload(Payload):
    kind: Literal["sim.agent.plan"]
    plan_id: str
    entity: EntityName
    day: str
    revision: int = Field(ge=1)
    blocks: tuple[PlanBlock, ...] = Field(min_length=1)

"""InterruptEngine: one event delivered per step, everything else follows.

Step anatomy: pop the earliest scheduled draft, mint it into a world event,
flush expired attention, route and deliver observations (parallel, ordered),
ask the game master who acts, collect actions (parallel, ordered), resolve
sequentially, schedule the resulting drafts, check termination.

Ordering guarantees: asyncio.gather preserves input order; input order is
always entity declaration order; shared state (queue, log, attention) is
mutated only between gathers, never inside entity tasks.
"""

import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.actions import ActionSpec, EntityAction
from workbench.core.events import Event
from workbench.core.simtime import SimTime
from workbench.core.worldlog import WorldLogWriter
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.queue import EventQueue, ScheduledEvent
from workbench.simulation.entity.entity import Entity
from workbench.simulation.gm.game_master import GameMaster
from workbench.simulation.time_model import TimeModel


class StopCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int | None = None
    end_time: int | None = None


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    step: int
    event: Event
    observers: tuple[str, ...]
    actions: tuple[tuple[str, EntityAction], ...]
    scheduled: tuple[ScheduledEvent, ...]
    terminated: bool


class RunResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: int = Field(ge=0)
    reason: Literal["terminated", "quiescent", "max_steps", "end_time"]
    final_time: int = Field(ge=0)


class InterruptEngine:
    def __init__(
        self,
        *,
        entities: tuple[Entity, ...],
        game_master: GameMaster,
        time_model: TimeModel,
        queue: EventQueue,
        attention: AttentionBook,
        world_log: WorldLogWriter,
        next_seq: int,
        next_order: int,
        step: int = 0,
    ) -> None:
        self._entities = {entity.name: entity for entity in entities}
        self._entity_order = tuple(entity.name for entity in entities)
        self._gm = game_master
        self._time = time_model
        self._queue = queue
        self._attention = attention
        self._log = world_log
        self._next_seq = next_seq
        self._next_order = next_order
        self._step = step

    @property
    def step_count(self) -> int:
        return self._step

    @property
    def next_seq(self) -> int:
        return self._next_seq

    @property
    def next_order(self) -> int:
        return self._next_order

    def queue_length(self) -> int:
        return len(self._queue)

    async def _flush_expired(self, now: SimTime) -> None:
        for name in self._entity_order:
            flushable = self._attention.flushable(name, now=now)
            if not flushable:
                continue
            for event in self._attention.flush(name):
                await self._entities[name].observe(event)
            self._attention.clear(name)

    async def step(self) -> StepResult:
        item = self._queue.pop()
        event_time = SimTime(max(item.time, int(self._time.now())))
        await self._time.wait_until(event_time)
        self._time.advance_to(event_time)

        event = item.draft.to_event(seq=self._next_seq, time=event_time)
        self._next_seq += 1
        self._log.append(event)

        await self._flush_expired(event_time)

        routed = await self._gm.route(event)
        observers: list[str] = []
        for name in routed:
            if name not in self._entities:
                continue
            if self._attention.should_deliver(name, event, now=event_time):
                observers.append(name)
            else:
                self._attention.defer(name, event)
        await asyncio.gather(
            *(self._entities[name].observe(event) for name in observers)
        )

        decision = await self._gm.next_acting(event)
        acting = tuple(
            name for name in decision.entities if name in self._entities
        )
        specs: list[ActionSpec] = []
        for name in acting:
            specs.append(await self._gm.action_spec_for(name, event))
        actions = await asyncio.gather(
            *(
                self._entities[name].act(spec)
                for name, spec in zip(acting, specs, strict=True)
            )
        )

        scheduled: list[ScheduledEvent] = []
        for name, action, spec in zip(acting, actions, specs, strict=True):
            resolution = await self._gm.resolve(name, action, spec, event)
            for draft in resolution.drafts:
                item = ScheduledEvent(
                    time=int(event_time) + int(draft.delay),
                    order=self._next_order,
                    draft=draft,
                )
                self._next_order += 1
                self._queue.push(item)
                scheduled.append(item)

        terminate = await self._gm.should_terminate()
        result = StepResult(
            step=self._step,
            event=event,
            observers=tuple(observers),
            actions=tuple(zip(acting, actions, strict=True)),
            scheduled=tuple(scheduled),
            terminated=terminate.terminate,
        )
        self._step += 1
        return result

    async def run(self, stop: StopCondition) -> RunResult:
        steps = 0
        while True:
            if stop.max_steps is not None and steps >= stop.max_steps:
                return self._result(steps, "max_steps")
            if len(self._queue) == 0:
                return self._result(steps, "quiescent")
            if (
                stop.end_time is not None
                and self._queue.peek().time > stop.end_time
            ):
                return self._result(steps, "end_time")
            result = await self.step()
            steps += 1
            if result.terminated:
                return self._result(steps, "terminated")

    def _result(
        self,
        steps: int,
        reason: Literal["terminated", "quiescent", "max_steps", "end_time"],
    ) -> RunResult:
        return RunResult(
            steps=steps, reason=reason, final_time=int(self._time.now())
        )

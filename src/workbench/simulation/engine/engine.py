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
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from workbench.simulation.snapshot import EngineState

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.actions import ActionSpec, EntityAction
from workbench.core.events import Event
from workbench.core.simtime import SimTime
from workbench.core.store import SqliteRunStore
from workbench.core.worldlog import WorldLogWriter
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.queue import EventQueue, ScheduledEvent
from workbench.simulation.entity.entity import Entity
from workbench.simulation.errors import ConfigError
from workbench.simulation.gm.game_master import GameMaster
from workbench.simulation.time_model import TimeModel


class StopCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int | None = None
    end_time: int | None = None
    # Cooperative interrupt: checked between steps, so the current step
    # always finishes and commits before the run stops.
    stop_requested: Callable[[], bool] | None = None


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
    reason: Literal[
        "terminated", "quiescent", "max_steps", "end_time", "interrupted"
    ]
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
        world_log: WorldLogWriter | None = None,
        store: SqliteRunStore | None = None,
        next_seq: int,
        next_order: int,
        step: int = 0,
    ) -> None:
        if (world_log is None) == (store is None):
            raise ConfigError("engine needs exactly one of world_log or store")
        self._entities = {entity.name: entity for entity in entities}
        self._entity_order = tuple(entity.name for entity in entities)
        self._gm = game_master
        self._time = time_model
        self._queue = queue
        self._attention = attention
        self._log = world_log
        self._store = store
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

    def add_entity(self, entity: Entity) -> None:
        """Grow the cast. Only call between steps (an ``on_step`` callback):
        mid-step the observer/acting gathers already hold the old roster."""
        if entity.name in self._entities:
            raise ConfigError(f"engine already has an entity named {entity.name!r}")
        self._entities[entity.name] = entity
        self._entity_order = (*self._entity_order, entity.name)
        self._attention.add_entity(entity.name)

    def capture_state(self) -> EngineState:
        # Imported here: snapshot.py imports engine types at module level.
        from workbench.simulation.snapshot import EngineState

        return EngineState(
            step=self._step,
            next_seq=self._next_seq,
            next_order=self._next_order,
            time=self._time.get_state(),
            queue=self._queue.snapshot(),
            attention=self._attention.get_state(),
            entities=tuple(
                self._entities[name].snapshot() for name in sorted(self._entity_order)
            ),
            game_master=self._gm.get_state().model_dump(mode="json"),
        )

    def restore_state(self, state: EngineState) -> None:
        from pydantic import ValidationError

        from workbench.simulation.errors import SnapshotError

        own_names = set(self._entity_order)
        snap_names = {snap.entity for snap in state.entities}
        if own_names != snap_names:
            raise SnapshotError(
                f"entity mismatch: engine has {sorted(own_names)}, "
                f"snapshot has {sorted(snap_names)}"
            )
        self._step = state.step
        self._next_seq = state.next_seq
        self._next_order = state.next_order
        self._time.set_state(state.time)
        fresh_queue = EventQueue()
        for item in state.queue:
            fresh_queue.push(item)
        self._queue = fresh_queue
        self._attention.set_state(state.attention)
        for snap in state.entities:
            self._entities[snap.entity].restore(snap)
        try:
            gm_state = self._gm.state_model.model_validate(state.game_master)
        except ValidationError as error:
            raise SnapshotError(
                f"game-master state failed validation: {error}"
            ) from error
        self._gm.set_state(gm_state)

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
        popped_order = item.order
        event_time = SimTime(max(item.time, int(self._time.now())))
        await self._time.wait_until(event_time)
        self._time.advance_to(event_time)

        event = item.draft.to_event(seq=self._next_seq, time=event_time)
        self._next_seq += 1
        if self._log is not None:
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
        acting = tuple(name for name in decision.entities if name in self._entities)
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

        for draft in await self._gm.consequences(event):
            item = ScheduledEvent(
                time=int(event_time) + int(draft.delay),
                order=self._next_order,
                draft=draft,
            )
            self._next_order += 1
            self._queue.push(item)
            scheduled.append(item)

        terminate = await self._gm.should_terminate()
        if self._store is not None:
            # The step becomes durable here, or not at all: a crash anywhere
            # earlier leaves the queue row in place and the step re-executes
            # on resume, replaying its LM calls from the cassette.
            with self._store.transaction():
                self._store.append_event(event)
                self._store.queue_remove(order=popped_order)
                for entry in scheduled:
                    self._store.queue_add(
                        time=entry.time, order=entry.order, draft=entry.draft
                    )
                self._store.set_meta("step", str(self._step + 1))
                self._store.set_meta("next_order", str(self._next_order))
                self._store.set_meta(
                    "gm_state", self._gm.get_state().model_dump_json()
                )
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

    async def step_batch(self, window: int) -> tuple[StepResult, ...]:
        """Execute up to ``window`` same-time, footprint-disjoint steps with
        every entity act across the batch running concurrently.

        Admission scans the queue in canonical (time, order) order and stops
        at the first conflict, so the executed sequence is always a canonical
        prefix — the world log is byte-identical for every window size. The
        whole batch commits in one transaction: durability moves from
        per-step to per-batch, and a crash re-executes the batch from its
        boundary (cassette replay makes that cheap)."""

        from workbench.core.footprint import footprint_of

        if self._store is None:
            raise ConfigError("windowed execution requires store mode")
        preview = getattr(self._gm, "observers_for", None)

        first = self._queue.pop()
        now = int(self._time.now())
        head_time = SimTime(max(first.time, now))
        admitted = [first]
        footprints = [footprint_of(first.draft.payload)]
        entity_sets = [
            set(preview(first.draft.payload)) if preview is not None else set()
        ]
        # A GM without a pure routing preview gets batches of one.
        while preview is not None and len(admitted) < window and len(self._queue):
            candidate = self._queue.peek()
            if max(candidate.time, now) != int(head_time):
                break
            footprint = footprint_of(candidate.draft.payload)
            entities = set(preview(candidate.draft.payload))
            if any(footprint.conflicts(other) for other in footprints) or any(
                entities & seen for seen in entity_sets
            ):
                break
            admitted.append(self._queue.pop())
            footprints.append(footprint)
            entity_sets.append(entities)

        await self._time.wait_until(head_time)
        self._time.advance_to(head_time)
        await self._flush_expired(head_time)

        contexts: list[
            tuple[ScheduledEvent, Event, tuple[str, ...], tuple[str, ...], tuple]
        ] = []
        for item in admitted:
            event = item.draft.to_event(seq=self._next_seq, time=head_time)
            self._next_seq += 1
            routed = await self._gm.route(event)
            observers: list[str] = []
            for name in routed:
                if name not in self._entities:
                    continue
                if self._attention.should_deliver(name, event, now=head_time):
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
            specs = tuple(
                [await self._gm.action_spec_for(name, event) for name in acting]
            )
            contexts.append((item, event, tuple(observers), acting, specs))

        # The parallel phase: disjoint footprints guarantee no act's inputs
        # depend on another batch member, so canonical gather order plus
        # per-entity call seeds keep replay deterministic.
        flat = [
            (index, name, spec)
            for index, (_, _, _, acting, specs) in enumerate(contexts)
            for name, spec in zip(acting, specs, strict=True)
        ]
        all_actions = await asyncio.gather(
            *(self._entities[name].act(spec) for _, name, spec in flat)
        )
        actions_by_step: dict[int, list[EntityAction]] = {}
        for (index, _, _), action in zip(flat, all_actions, strict=True):
            actions_by_step.setdefault(index, []).append(action)

        results: list[StepResult] = []
        for index, (_item, event, observers, acting, specs) in enumerate(contexts):
            actions = tuple(actions_by_step.get(index, ()))
            scheduled: list[ScheduledEvent] = []
            for name, action, spec in zip(acting, actions, specs, strict=True):
                resolution = await self._gm.resolve(name, action, spec, event)
                for draft in resolution.drafts:
                    entry = ScheduledEvent(
                        time=int(head_time) + int(draft.delay),
                        order=self._next_order,
                        draft=draft,
                    )
                    self._next_order += 1
                    self._queue.push(entry)
                    scheduled.append(entry)
            for draft in await self._gm.consequences(event):
                entry = ScheduledEvent(
                    time=int(head_time) + int(draft.delay),
                    order=self._next_order,
                    draft=draft,
                )
                self._next_order += 1
                self._queue.push(entry)
                scheduled.append(entry)
            terminate = await self._gm.should_terminate()
            if terminate.terminate and index < len(contexts) - 1:
                raise ConfigError(
                    "game master terminated mid-batch; a terminating game "
                    "master needs window=1"
                )
            results.append(
                StepResult(
                    step=self._step,
                    event=event,
                    observers=observers,
                    actions=tuple(zip(acting, actions, strict=True)),
                    scheduled=tuple(scheduled),
                    terminated=terminate.terminate,
                )
            )
            self._step += 1

        with self._store.transaction():
            for (item, event, _, _, _), result in zip(
                contexts, results, strict=True
            ):
                self._store.append_event(event)
                self._store.queue_remove(order=item.order)
                for entry in result.scheduled:
                    self._store.queue_add(
                        time=entry.time, order=entry.order, draft=entry.draft
                    )
            self._store.set_meta("step", str(self._step))
            self._store.set_meta("next_order", str(self._next_order))
            self._store.set_meta("gm_state", self._gm.get_state().model_dump_json())
        return tuple(results)

    async def run(
        self,
        stop: StopCondition,
        *,
        on_step: Callable[[StepResult], None] | None = None,
        on_batch: Callable[[tuple[StepResult, ...]], None] | None = None,
        window: int = 1,
    ) -> RunResult:
        steps = 0
        while True:
            if stop.stop_requested is not None and stop.stop_requested():
                return self._result(steps, "interrupted")
            if stop.max_steps is not None and steps >= stop.max_steps:
                return self._result(steps, "max_steps")
            if len(self._queue) == 0:
                return self._result(steps, "quiescent")
            if stop.end_time is not None and self._queue.peek().time > stop.end_time:
                return self._result(steps, "end_time")
            if window <= 1:
                results: tuple[StepResult, ...] = (await self.step(),)
            else:
                allowance = window
                if stop.max_steps is not None:
                    allowance = min(allowance, stop.max_steps - steps)
                results = await self.step_batch(allowance)
            if on_batch is not None:
                on_batch(results)
            for result in results:
                steps += 1
                if on_step is not None:
                    on_step(result)
                if result.terminated:
                    return self._result(steps, "terminated")

    def _result(
        self,
        steps: int,
        reason: Literal[
        "terminated", "quiescent", "max_steps", "end_time", "interrupted"
    ],
    ) -> RunResult:
        return RunResult(steps=steps, reason=reason, final_time=int(self._time.now()))

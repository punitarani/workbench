"""Assemble and run a compiled workplace end to end, durably.

Every run is backed by ``run.db`` (events, queue, snapshots, metadata) with
one transaction per engine step, so a run can be interrupted at any point and
resumed from the latest committed step. ``world.jsonl`` is exported after
every run segment — byte-identical to the historical writer output — and
remains the canonical artifact downstream consumers read.
"""

import json
from collections.abc import Callable, Mapping
from pathlib import Path

from workbench.core.events import Event
from workbench.core.seed import Seed
from workbench.core.store import SqliteRunStore, export_jsonl
from workbench.core.worldlog import RunManifest, write_manifest
from workbench.simulation.actors.client import ClientActorAct
from workbench.simulation.calendar import CalendarWindow
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.engine import (
    InterruptEngine,
    RunResult,
    StepResult,
    StopCondition,
)
from workbench.simulation.engine.queue import EventQueue, ScheduledEvent
from workbench.simulation.entity.entity import ComposedEntity, Entity
from workbench.simulation.errors import ConfigError, ConfigMismatchError, SnapshotError
from workbench.simulation.external.entity import ExternalEntity
from workbench.simulation.external.transport import ActTransport
from workbench.simulation.gm.grounded import DayPlan, GroundedGm
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.lm.protocol import LanguageModel
from workbench.simulation.persona.actor import ProfessionalActorAct
from workbench.simulation.persona.memory_stream import MemoryStreamComponent
from workbench.simulation.persona.params import ProfessionalWorkerParams
from workbench.simulation.persona.programs import ProfessionalActor
from workbench.simulation.persona.working_memory import WorkingMemoryComponent
from workbench.simulation.snapshot import SimulationSnapshot
from workbench.simulation.time_model import EventDrivenTimeModel
from workbench.simulation.workplace.compile import CompiledWorkplace, compile_workplace
from workbench.simulation.workplace.spec import WorkplaceSpec

# Genesis facts everyone at the org can see, regardless of routing.
_PUBLIC_TAGS = (
    "person.record",
    "chat.conversation.created",
    "calendar.event.scheduled",
)


class _Runtime:
    def __init__(
        self,
        *,
        gm: GroundedGm,
        entities: tuple[Entity, ...],
        memories: dict[str, WorkingMemoryComponent],
        externals: dict[str, ExternalEntity],
        person_for_entity: dict[str, str | None],
        make_persona_entity: Callable[
            [str, ProfessionalWorkerParams],
            tuple[WorkingMemoryComponent, ComposedEntity],
        ],
        pending_arrivals: dict[str, tuple[str, ProfessionalWorkerParams]],
        lms: dict[str, WorkbenchLM],
        deep_lms: dict[str, WorkbenchLM],
        personas: dict[str, ComposedEntity],
    ) -> None:
        self.gm = gm
        self.entities = entities
        self.memories = memories
        self.externals = externals
        self.person_for_entity = person_for_entity
        self.make_persona_entity = make_persona_entity
        # person_id -> (entity_name, params) for scripted arrivals whose
        # person.record has not occurred yet.
        self.pending_arrivals = pending_arrivals
        # Registries the roll-forward resume and per-batch meta need:
        # every persona entity and its WorkbenchLM, arrivals included.
        self.lms = lms
        self.deep_lms = deep_lms
        self.personas = personas


def _build_runtime(
    compiled: CompiledWorkplace,
    *,
    seed: Seed,
    inner_lm: LanguageModel,
    model: str,
    external_seats: Mapping[str, ActTransport] | None,
    actor_factory: Callable[[], ProfessionalActor] | None,
    deep_model: str | None = None,
    director=None,
) -> _Runtime:
    from datetime import date, timedelta

    end = date.fromisoformat(compiled.start_date) + timedelta(days=compiled.days - 1)
    day_plan = DayPlan(
        window=CalendarWindow(
            start_date=compiled.start_date,
            end_date=end.isoformat(),
            timezone=compiled.timezone,
        ),
        personas=tuple(
            (entity_name, params.check_interval_minutes)
            for entity_name, params in compiled.personas
        ),
        end_of_day=compiled.end_of_day_seconds,
        wake_grid_minutes=compiled.wake_grid_minutes,
        timesheets=compiled.timesheets,
        seed_root=seed.root,
    )
    gm = GroundedGm(
        entity_for_person=dict(compiled.entity_for_person),
        ticket_vocabulary=compiled.ticket_vocabulary,
        day_plan=day_plan,
        delivery_quantum_seconds=compiled.delivery_quantum_seconds,
        director=director,
    )
    gm.set_state(GroundedGm.state_model(minter=compiled.minter.model_copy(deep=True)))
    gm.set_bill_rates(
        {
            params.person_id: params.bill_rate_cents
            for _, params in (*compiled.personas, *compiled.arrivals)
            if params.bill_rate_cents is not None
        }
    )

    vocab = compiled.ticket_vocabulary
    workplace_norms = (
        f"Ticket statuses: {', '.join(vocab.statuses)}. "
        f"Priorities: {', '.join(vocab.priorities)}. "
        f"Types: {', '.join(vocab.ticket_types)}."
    )
    seats = dict(external_seats or {})
    persona_names = {entity_name for entity_name, _ in compiled.personas}
    unknown_seats = sorted(set(seats) - persona_names)
    if unknown_seats:
        raise ConfigError(
            f"external seats name no persona in this workplace: {unknown_seats}"
        )

    lms: dict[str, WorkbenchLM] = {}
    deep_lms: dict[str, WorkbenchLM] = {}
    personas: dict[str, ComposedEntity] = {}

    def make_persona_entity(
        entity_name: str, params: ProfessionalWorkerParams
    ) -> tuple[WorkingMemoryComponent, ComposedEntity]:
        memory = WorkingMemoryComponent(
            person_id=params.person_id, start_date=compiled.start_date
        )
        stream = MemoryStreamComponent(
            person_id=params.person_id, entity_name=entity_name
        )
        lm = WorkbenchLM(
            inner_lm,
            model=model,
            seed=seed,
            path=("entity", entity_name),
        )
        deep_lm = (
            WorkbenchLM(
                inner_lm,
                model=deep_model,
                seed=seed,
                path=("entity", entity_name, "deep"),
            )
            if deep_model is not None
            else None
        )
        entity = ComposedEntity(
            name=entity_name,
            components=(memory, stream),
            act_component=ProfessionalActorAct(
                params=params,
                working_memory=memory,
                lm=lm,
                actor=actor_factory() if actor_factory is not None else None,
                workplace_norms=workplace_norms,
                memory_stream=stream,
                deep_lm=deep_lm,
            ),
        )
        lms[entity_name] = lm
        if deep_lm is not None:
            deep_lms[entity_name] = deep_lm
        personas[entity_name] = entity
        return memory, entity

    entities: list[Entity] = []
    memories: dict[str, WorkingMemoryComponent] = {}
    externals: dict[str, ExternalEntity] = {}
    for entity_name, params in compiled.personas:
        if entity_name in seats:
            external = ExternalEntity(name=entity_name, transport=seats[entity_name])
            entities.append(external)
            externals[entity_name] = external
            continue
        memory, entity = make_persona_entity(entity_name, params)
        entities.append(entity)
        memories[entity_name] = memory

    for entity_name, client_params in compiled.clients:
        client_memory = WorkingMemoryComponent(
            person_id=client_params.person_id, start_date=compiled.start_date
        )
        client_lm = WorkbenchLM(
            inner_lm,
            model=model,
            seed=seed,
            path=("entity", entity_name),
        )
        client_entity = ComposedEntity(
            name=entity_name,
            components=(client_memory,),
            act_component=ClientActorAct(
                params=client_params,
                working_memory=client_memory,
                lm=client_lm,
            ),
        )
        entities.append(client_entity)
        memories[entity_name] = client_memory
        lms[entity_name] = client_lm
        personas[entity_name] = client_entity

    person_for_entity = {
        entity: person for person, entity in compiled.entity_for_person
    }
    return _Runtime(
        gm=gm,
        entities=tuple(entities),
        memories=memories,
        externals=externals,
        person_for_entity=person_for_entity,
        make_persona_entity=make_persona_entity,
        pending_arrivals={
            params.person_id: (entity_name, params)
            for entity_name, params in compiled.arrivals
        },
        lms=lms,
        deep_lms=deep_lms,
        personas=personas,
    )


def _durable_meta(runtime: _Runtime) -> dict[str, str]:
    """Act-derived state committed with every step/batch so a resume
    without a usable snapshot can roll forward: per-entity LM call
    counters (seed continuity) and working-memory facts ledgers (the
    persona's own action summaries — they live in no world event)."""

    counters = {name: lm.calls for name, lm in sorted(runtime.lms.items())}
    deep_counters = {name: lm.calls for name, lm in sorted(runtime.deep_lms.items())}
    facts = {
        name: list(memory.facts()) for name, memory in sorted(runtime.memories.items())
    }
    return {
        "lm_calls": json.dumps(counters, sort_keys=True),
        "deep_lm_calls": json.dumps(deep_counters, sort_keys=True),
        "memory_facts": json.dumps(facts, sort_keys=True),
    }


async def _deliver_events(runtime: _Runtime, events) -> None:
    for event in events:
        observers = await runtime.gm.route(event)
        relevant = event.tag in _PUBLIC_TAGS or event.tag == "document.created"
        if relevant:
            deliver_to = [*runtime.memories, *runtime.externals]
        else:
            deliver_to = [
                name
                for name in observers
                if name in runtime.memories or name in runtime.externals
            ]
        for name in deliver_to:
            if not relevant and runtime.person_for_entity.get(name) is None:
                continue
            if name in runtime.externals:
                await runtime.externals[name].observe(event)
            else:
                # Full entity observation: every component (working memory,
                # memory stream, and whatever arrives later) sees genesis.
                await runtime.personas[name].observe(event)


def _finish(
    store: SqliteRunStore,
    out_dir: Path,
    compiled: CompiledWorkplace,
    seed: Seed,
    result: RunResult,
) -> RunResult:
    log_path = out_dir / "world.jsonl"
    export_jsonl(store, log_path)
    manifest = RunManifest.for_log(
        log_path,
        run_id=f"run-{compiled.workplace_id}-{seed.root}",
        seed_root=seed.root,
        workplace_id=compiled.workplace_id,
        config_hash=compiled.config_hash,
    )
    write_manifest(manifest, out_dir / "manifest.json")
    store.close()
    return result


def _arrival_admitter(
    runtime: _Runtime, engine: InterruptEngine
) -> Callable[[StepResult], None]:
    """When a pending arrival's person.record hits the log, build their
    persona entity and grow the cast — between steps, so the engine's
    in-flight gathers never see a half-admitted roster."""

    def admit(result: StepResult) -> None:
        if result.event.tag != "person.record":
            return
        pending = runtime.pending_arrivals.pop(result.event.payload.person_id, None)
        if pending is None:
            return
        entity_name, params = pending
        memory, entity = runtime.make_persona_entity(entity_name, params)
        engine.add_entity(entity)
        runtime.memories[entity_name] = memory

    return admit


def _on_step(
    runtime: _Runtime,
    engine: InterruptEngine,
    store: SqliteRunStore,
    every: int,
    extra: Callable[[StepResult], None] | None = None,
) -> Callable[[StepResult], None]:
    admit = _arrival_admitter(runtime, engine)
    checkpoint = _checkpointer(engine, store, every)

    def on_step(result: StepResult) -> None:
        # Admission precedes the checkpoint so a snapshot taken on the
        # arrival step already covers the grown cast.
        admit(result)
        checkpoint(result)
        if extra is not None:
            extra(result)

    return on_step


_SNAPSHOTS_KEPT = 4


def _take_snapshot(engine: InterruptEngine, store: SqliteRunStore, step: int) -> None:
    snapshot = SimulationSnapshot(
        config_hash=store.get_meta("config_hash") or "",
        seed_root=int(store.get_meta("seed_root") or "0"),
        world_log_length=engine.next_seq,
        engine=engine.capture_state(),
    )
    store.put_snapshot(
        step=step,
        taken_seq=engine.next_seq,
        state=snapshot.model_dump_json(),
    )
    store.prune_snapshots(keep=_SNAPSHOTS_KEPT)
    store.commit()


def _checkpointer(
    engine: InterruptEngine, store: SqliteRunStore, every: int
) -> Callable[[StepResult], None]:
    def checkpoint(result: StepResult) -> None:
        if (result.step + 1) % every != 0:
            return
        _take_snapshot(engine, store, result.step + 1)

    return checkpoint


async def run_workplace(
    spec: WorkplaceSpec,
    *,
    seed: Seed,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    deep_model: str | None = None,
    director=None,
    on_step: Callable[[StepResult], None] | None = None,
    on_batch=None,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
    window: int = 1,
) -> RunResult:
    compiled = compile_workplace(spec, seed)
    return await run_compiled(
        compiled,
        seed=seed,
        out_dir=out_dir,
        inner_lm=inner_lm,
        model=model,
        deep_model=deep_model,
        director=director,
        on_step=on_step,
        on_batch=on_batch,
        stop=stop,
        external_seats=external_seats,
        actor_factory=actor_factory,
        checkpoint_every=checkpoint_every,
        window=window,
    )


async def run_compiled(
    compiled: CompiledWorkplace,
    *,
    seed: Seed,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    deep_model: str | None = None,
    director=None,
    on_step: Callable[[StepResult], None] | None = None,
    on_batch=None,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
    history: tuple[Event, ...] = (),
    window: int = 1,
) -> RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = _build_runtime(
        compiled,
        seed=seed,
        inner_lm=inner_lm,
        model=model,
        external_seats=external_seats,
        actor_factory=actor_factory,
        deep_model=deep_model,
        director=director,
    )

    store = SqliteRunStore.create(out_dir / "run.db")
    for event in history:
        store.append_event(event)
    for event in compiled.genesis:
        store.append_event(event)
    for item in compiled.scheduled:
        store.queue_add(time=item.time, order=item.order, draft=item.draft)
    store.set_meta("config_hash", compiled.config_hash)
    store.set_meta("seed_root", str(seed.root))
    store.set_meta("workplace_id", compiled.workplace_id)
    store.set_meta("model", model)
    store.set_meta("step", "0")
    store.set_meta("next_order", str(len(compiled.scheduled)))
    # The boundary between the broadcast-delivered opening world (history
    # plus genesis) and engine-minted events: roll-forward resume replays
    # each side with its own delivery semantics.
    store.set_meta("initial_seq", str(len(history) + len(compiled.genesis)))
    store.commit()

    await _deliver_events(runtime, history)
    await _deliver_events(runtime, compiled.genesis)
    store.set_meta("gm_state", runtime.gm.get_state().model_dump_json())
    store.commit()

    queue = EventQueue()
    for item in compiled.scheduled:
        queue.push(item)

    engine = InterruptEngine(
        entities=runtime.entities,
        game_master=runtime.gm,
        time_model=EventDrivenTimeModel(now=0),
        queue=queue,
        attention=AttentionBook(entities=tuple(e.name for e in runtime.entities)),
        store=store,
        next_seq=len(history) + len(compiled.genesis),
        next_order=len(compiled.scheduled),
        meta_extra=lambda: _durable_meta(runtime),
    )
    result = await engine.run(
        stop if stop is not None else StopCondition(end_time=compiled.end_time),
        on_step=_on_step(runtime, engine, store, checkpoint_every, on_step),
        on_batch=on_batch,
        window=window,
    )
    if result.reason == "interrupted":
        # A graceful stop earns a snapshot at the head so the next resume
        # takes the fast path regardless of checkpoint cadence.
        _take_snapshot(engine, store, int(store.get_meta("step") or "0"))
    return _finish(store, out_dir, compiled, seed, result)


async def resume_workplace(
    spec: WorkplaceSpec,
    *,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    deep_model: str | None = None,
    director=None,
    on_step: Callable[[StepResult], None] | None = None,
    on_batch=None,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
    window: int = 1,
) -> RunResult:
    """Continue a run from its latest committed state."""

    store = SqliteRunStore.open(out_dir / "run.db")
    stored_seed = Seed(root=int(store.get_meta("seed_root") or "0"))
    compiled = compile_workplace(spec, stored_seed)
    stored_hash = store.get_meta("config_hash")
    if stored_hash != compiled.config_hash:
        store.close()
        raise ConfigMismatchError(
            f"run.db was created under config {stored_hash}, "
            f"resume compiled {compiled.config_hash}"
        )

    runtime = _build_runtime(
        compiled,
        seed=stored_seed,
        inner_lm=inner_lm,
        model=model,
        external_seats=external_seats,
        actor_factory=actor_factory,
        deep_model=deep_model,
        director=director,
    )

    stored = store.latest_snapshot()
    head_seq, head_time = store.head()
    if stored is not None and stored.taken_seq == head_seq:
        engine = InterruptEngine(
            entities=runtime.entities,
            game_master=runtime.gm,
            time_model=EventDrivenTimeModel(now=0),
            queue=EventQueue(),
            attention=AttentionBook(entities=tuple(e.name for e in runtime.entities)),
            store=store,
            next_seq=0,
            next_order=0,
            meta_extra=lambda: _durable_meta(runtime),
        )
        snapshot = SimulationSnapshot.model_validate_json(stored.state)
        stored_events = tuple(store.read_events())
        # Scripted arrivals that already happened grew the cast; rebuild
        # those entities (in event order, matching the straight run) before
        # the restore's roster check.
        arrived: list[Entity] = []
        for event in stored_events:
            if event.tag != "person.record":
                continue
            pending = runtime.pending_arrivals.pop(event.payload.person_id, None)
            if pending is None:
                continue
            entity_name, params = pending
            memory, entity = runtime.make_persona_entity(entity_name, params)
            engine.add_entity(entity)
            runtime.memories[entity_name] = memory
            arrived.append(entity)
        engine.restore_state(snapshot.engine)
        # Working memories snapshot event ids only; refill them from the
        # single copy of every event — the store.
        events_by_id = {str(e.event_id): e for e in stored_events}
        for entity in (*runtime.entities, *arrived):
            for component in getattr(entity, "components", ()):
                rehydrate = getattr(component, "rehydrate", None)
                if rehydrate is not None:
                    rehydrate(events_by_id)
    else:
        # Roll-forward: no snapshot at the head (killed mid-cadence, or
        # never checkpointed). Rebuild live state by replaying the log with
        # the same delivery semantics the original run used — the opening
        # world (history + genesis) is broadcast, engine-minted events go
        # only to their routed observers — then restore the committed GM
        # state, queue, and per-entity LM counters from meta.
        initial_meta = store.get_meta("initial_seq")
        if initial_meta is None:
            store.close()
            raise SnapshotError(
                "run.db has no snapshot at the head and predates roll-forward "
                "resume (missing initial_seq meta); re-run or checkpoint denser"
            )
        stored_events = tuple(store.read_events())
        initial = int(initial_meta)
        await _deliver_events(runtime, stored_events[:initial])
        arrived_entities: list[Entity] = []
        for event in stored_events[initial:]:
            observers = await runtime.gm.route(event)
            for name in observers:
                if name in runtime.externals:
                    await runtime.externals[name].observe(event)
                elif name in runtime.personas:
                    await runtime.personas[name].observe(event)
            # Admission follows delivery, exactly like the live run: the
            # arriving entity never observes its own person.record.
            if event.tag == "person.record":
                pending = runtime.pending_arrivals.pop(event.payload.person_id, None)
                if pending is not None:
                    entity_name, params = pending
                    memory, entity = runtime.make_persona_entity(entity_name, params)
                    runtime.memories[entity_name] = memory
                    arrived_entities.append(entity)
        gm_state = store.get_meta("gm_state")
        if gm_state is not None:
            runtime.gm.set_state(runtime.gm.state_model.model_validate_json(gm_state))
        counters = json.loads(store.get_meta("lm_calls") or "{}")
        for name, lm in runtime.lms.items():
            lm.set_calls(int(counters.get(name, 0)))
        deep_counters = json.loads(store.get_meta("deep_lm_calls") or "{}")
        for name, lm in runtime.deep_lms.items():
            lm.set_calls(int(deep_counters.get(name, 0)))
        facts = json.loads(store.get_meta("memory_facts") or "{}")
        for name, memory in runtime.memories.items():
            memory.restore_facts(tuple(facts.get(name, ())))
        queue = EventQueue()
        for time, order, draft in store.queue_rows():
            queue.push(ScheduledEvent(time=time, order=order, draft=draft))
        roster = (*runtime.entities, *arrived_entities)
        engine = InterruptEngine(
            entities=roster,
            game_master=runtime.gm,
            time_model=EventDrivenTimeModel(now=head_time),
            queue=queue,
            attention=AttentionBook(entities=tuple(e.name for e in roster)),
            store=store,
            next_seq=head_seq,
            next_order=int(store.get_meta("next_order") or "0"),
            step=int(store.get_meta("step") or "0"),
            meta_extra=lambda: _durable_meta(runtime),
        )

    result = await engine.run(
        stop if stop is not None else StopCondition(end_time=compiled.end_time),
        on_step=_on_step(runtime, engine, store, checkpoint_every, on_step),
        on_batch=on_batch,
        window=window,
    )
    if result.reason == "interrupted":
        _take_snapshot(engine, store, int(store.get_meta("step") or "0"))
    return _finish(store, out_dir, compiled, seed=stored_seed, result=result)

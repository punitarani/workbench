"""Assemble and run a compiled workplace end to end, durably.

Every run is backed by ``run.db`` (events, queue, snapshots, metadata) with
one transaction per engine step, so a run can be interrupted at any point and
resumed from the latest committed step. ``world.jsonl`` is exported after
every run segment — byte-identical to the historical writer output — and
remains the canonical artifact downstream consumers read.
"""

from collections.abc import Callable, Mapping
from pathlib import Path

from workbench.core.seed import Seed
from workbench.core.store import SqliteRunStore, export_jsonl
from workbench.core.worldlog import RunManifest, write_manifest
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
from workbench.simulation.gm.grounded import GroundedGm
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.lm.protocol import LanguageModel
from workbench.simulation.persona.actor import ProfessionalActorAct
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
    ) -> None:
        self.gm = gm
        self.entities = entities
        self.memories = memories
        self.externals = externals
        self.person_for_entity = person_for_entity


def _build_runtime(
    compiled: CompiledWorkplace,
    *,
    seed: Seed,
    inner_lm: LanguageModel,
    model: str,
    external_seats: Mapping[str, ActTransport] | None,
    actor_factory: Callable[[], ProfessionalActor] | None,
) -> _Runtime:
    gm = GroundedGm(
        entity_for_person=dict(compiled.entity_for_person),
        ticket_vocabulary=compiled.ticket_vocabulary,
    )
    gm.set_state(GroundedGm.state_model(minter=compiled.minter.model_copy(deep=True)))

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

    entities: list[Entity] = []
    memories: dict[str, WorkingMemoryComponent] = {}
    externals: dict[str, ExternalEntity] = {}
    for entity_name, params in compiled.personas:
        if entity_name in seats:
            external = ExternalEntity(name=entity_name, transport=seats[entity_name])
            entities.append(external)
            externals[entity_name] = external
            continue
        memory = WorkingMemoryComponent(person_id=params.person_id)
        lm = WorkbenchLM(
            inner_lm,
            model=model,
            seed=seed,
            path=("entity", entity_name),
        )
        entities.append(
            ComposedEntity(
                name=entity_name,
                components=(memory,),
                act_component=ProfessionalActorAct(
                    params=params,
                    working_memory=memory,
                    lm=lm,
                    actor=actor_factory() if actor_factory is not None else None,
                    workplace_norms=workplace_norms,
                ),
            )
        )
        memories[entity_name] = memory

    person_for_entity = {
        entity: person for person, entity in compiled.entity_for_person
    }
    return _Runtime(
        gm=gm,
        entities=tuple(entities),
        memories=memories,
        externals=externals,
        person_for_entity=person_for_entity,
    )


async def _deliver_genesis(runtime: _Runtime, compiled: CompiledWorkplace) -> None:
    for event in compiled.genesis:
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
                await runtime.memories[name].pre_observe(event)


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


def _checkpointer(
    engine: InterruptEngine, store: SqliteRunStore, every: int
) -> Callable[[StepResult], None]:
    def checkpoint(result: StepResult) -> None:
        if (result.step + 1) % every != 0:
            return
        snapshot = SimulationSnapshot(
            config_hash=store.get_meta("config_hash") or "",
            seed_root=int(store.get_meta("seed_root") or "0"),
            world_log_length=engine.next_seq,
            engine=engine.capture_state(),
        )
        store.put_snapshot(
            step=result.step + 1,
            taken_seq=engine.next_seq,
            state=snapshot.model_dump_json(),
        )
        store.commit()

    return checkpoint


async def run_workplace(
    spec: WorkplaceSpec,
    *,
    seed: Seed,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
) -> RunResult:
    compiled = compile_workplace(spec, seed)
    return await run_compiled(
        compiled,
        seed=seed,
        out_dir=out_dir,
        inner_lm=inner_lm,
        model=model,
        stop=stop,
        external_seats=external_seats,
        actor_factory=actor_factory,
        checkpoint_every=checkpoint_every,
    )


async def run_compiled(
    compiled: CompiledWorkplace,
    *,
    seed: Seed,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
) -> RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = _build_runtime(
        compiled,
        seed=seed,
        inner_lm=inner_lm,
        model=model,
        external_seats=external_seats,
        actor_factory=actor_factory,
    )

    store = SqliteRunStore.create(out_dir / "run.db")
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
    store.commit()

    await _deliver_genesis(runtime, compiled)
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
        next_seq=len(compiled.genesis),
        next_order=len(compiled.scheduled),
    )
    result = await engine.run(
        stop if stop is not None else StopCondition(end_time=compiled.end_time),
        on_step=_checkpointer(engine, store, checkpoint_every),
    )
    return _finish(store, out_dir, compiled, seed, result)


async def resume_workplace(
    spec: WorkplaceSpec,
    *,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
    actor_factory: Callable[[], ProfessionalActor] | None = None,
    checkpoint_every: int = 1,
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
    )

    engine = InterruptEngine(
        entities=runtime.entities,
        game_master=runtime.gm,
        time_model=EventDrivenTimeModel(now=0),
        queue=EventQueue(),
        attention=AttentionBook(
            entities=tuple(e.name for e in runtime.entities)
        ),
        store=store,
        next_seq=0,
        next_order=0,
    )

    stored = store.latest_snapshot()
    if stored is not None:
        if stored.taken_seq != store.head()[0]:
            store.close()
            raise SnapshotError(
                f"latest snapshot covers seq {stored.taken_seq} but the store "
                f"head is {store.head()[0]}; commits after the snapshot need "
                "a denser checkpoint cadence"
            )
        snapshot = SimulationSnapshot.model_validate_json(stored.state)
        engine.restore_state(snapshot.engine)
        # Working memories snapshot event ids only; refill them from the
        # single copy of every event — the store.
        events_by_id = {str(e.event_id): e for e in store.read_events()}
        for entity in runtime.entities:
            for component in getattr(entity, "components", ()):
                rehydrate = getattr(component, "rehydrate", None)
                if rehydrate is not None:
                    rehydrate(events_by_id)
    else:
        # Interrupted before the first checkpoint: rebuild the start-of-day
        # state exactly as a fresh run does, from the compiled workplace.
        await _deliver_genesis(runtime, compiled)
        gm_state = store.get_meta("gm_state")
        if gm_state is not None:
            runtime.gm.set_state(
                runtime.gm.state_model.model_validate_json(gm_state)
            )
        queue = EventQueue()
        for time, order, draft in store.queue_rows():
            queue.push(ScheduledEvent(time=time, order=order, draft=draft))
        engine = InterruptEngine(
            entities=runtime.entities,
            game_master=runtime.gm,
            time_model=EventDrivenTimeModel(now=store.head()[1]),
            queue=queue,
            attention=AttentionBook(
                entities=tuple(e.name for e in runtime.entities)
            ),
            store=store,
            next_seq=store.head()[0],
            next_order=int(store.get_meta("next_order") or "0"),
            step=int(store.get_meta("step") or "0"),
        )

    result = await engine.run(
        stop if stop is not None else StopCondition(end_time=compiled.end_time),
        on_step=_checkpointer(engine, store, checkpoint_every),
    )
    return _finish(store, out_dir, compiled, seed=stored_seed, result=result)

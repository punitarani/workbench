"""Assemble and run a compiled workplace end to end."""

from collections.abc import Mapping
from pathlib import Path

from workbench.core.seed import Seed
from workbench.core.worldlog import RunManifest, WorldLogWriter, write_manifest
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.engine import (
    InterruptEngine,
    RunResult,
    StopCondition,
)
from workbench.simulation.engine.queue import EventQueue
from workbench.simulation.entity.entity import ComposedEntity, Entity
from workbench.simulation.errors import ConfigError
from workbench.simulation.external.entity import ExternalEntity
from workbench.simulation.external.transport import ActTransport
from workbench.simulation.gm.grounded import GroundedGm
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.lm.protocol import LanguageModel
from workbench.simulation.persona.actor import ProfessionalActorAct
from workbench.simulation.persona.working_memory import WorkingMemoryComponent
from workbench.simulation.time_model import EventDrivenTimeModel
from workbench.simulation.workplace.compile import CompiledWorkplace, compile_workplace
from workbench.simulation.workplace.spec import WorkplaceSpec

# Genesis facts everyone at the org can see, regardless of routing.
_PUBLIC_TAGS = (
    "person.record",
    "chat.conversation.created",
    "calendar.event.scheduled",
)


async def run_workplace(
    spec: WorkplaceSpec,
    *,
    seed: Seed,
    out_dir: Path,
    inner_lm: LanguageModel,
    model: str,
    stop: StopCondition | None = None,
    external_seats: Mapping[str, ActTransport] | None = None,
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
) -> RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "world.jsonl"

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
                    workplace_norms=workplace_norms,
                ),
            )
        )
        memories[entity_name] = memory

    person_for_entity = {
        entity: person for person, entity in compiled.entity_for_person
    }
    with WorldLogWriter(log_path) as writer:
        for event in compiled.genesis:
            writer.append(event)
            observers = await gm.route(event)
            relevant = event.tag in _PUBLIC_TAGS or event.tag == "document.created"
            if relevant:
                deliver_to = [*memories, *externals]
            else:
                deliver_to = [
                    name for name in observers if name in memories or name in externals
                ]
            for name in deliver_to:
                if not relevant and person_for_entity.get(name) is None:
                    continue
                if name in externals:
                    await externals[name].observe(event)
                else:
                    await memories[name].pre_observe(event)

        queue = EventQueue()
        for item in compiled.scheduled:
            queue.push(item)

        engine = InterruptEngine(
            entities=tuple(entities),
            game_master=gm,
            time_model=EventDrivenTimeModel(now=0),
            queue=queue,
            attention=AttentionBook(entities=tuple(e.name for e in entities)),
            world_log=writer,
            next_seq=len(compiled.genesis),
            next_order=len(compiled.scheduled),
        )
        result = await engine.run(
            stop if stop is not None else StopCondition(end_time=compiled.end_time)
        )

    manifest = RunManifest.for_log(
        log_path,
        run_id=f"run-{compiled.workplace_id}-{seed.root}",
        seed_root=seed.root,
        workplace_id=compiled.workplace_id,
        config_hash=compiled.config_hash,
    )
    write_manifest(manifest, out_dir / "manifest.json")
    return result

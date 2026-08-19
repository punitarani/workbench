"""Working-memory snapshots carry event ids, not event bodies."""

import pytest
from persona_fixtures import observed_events

from simulation.errors import SnapshotError
from simulation.persona.working_memory import WorkingMemoryComponent


async def hydrated() -> WorkingMemoryComponent:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    return memory


async def test_state_contains_ids_not_bodies() -> None:
    memory = await hydrated()
    dump = memory.get_state().model_dump_json()
    assert "Can you review the attached NDA" not in dump, (
        "snapshots must not embed event bodies"
    )
    assert "evt-000003" in dump
    assert len(dump) < 2_000


async def test_restore_requires_rehydration_and_round_trips() -> None:
    memory = await hydrated()
    state = memory.get_state()
    original_pending = memory.pending_items()

    fresh = WorkingMemoryComponent(person_id="per-daniel-reyes")
    fresh.set_state(state)
    with pytest.raises(SnapshotError):
        fresh.events()

    events_by_id = {e.event_id: e for e in observed_events()}
    fresh.rehydrate(events_by_id)
    assert fresh.events() == tuple(observed_events())
    assert fresh.pending_items() == original_pending
    assert fresh.facts() == memory.facts()


async def test_rehydrate_missing_id_raises() -> None:
    memory = await hydrated()
    state = memory.get_state()
    fresh = WorkingMemoryComponent(person_id="per-daniel-reyes")
    fresh.set_state(state)
    with pytest.raises(SnapshotError):
        fresh.rehydrate({})

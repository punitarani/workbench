"""ComposedEntity: components run through the phase machine, in declaration order.

Concurrency note: component hooks are awaited with asyncio.gather in
declaration order, and gather returns results in input order — ordering is
deterministic regardless of completion order.
"""

import asyncio
from typing import Protocol

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from workbench.core.actions import ActionSpec, EntityAction
from workbench.core.events import Event
from workbench.simulation.entity.acting import ActComponent
from workbench.simulation.entity.component import (
    Component,
    Phase,
    check_successor,
)
from workbench.simulation.errors import SnapshotError


class EntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity: str
    components: tuple[tuple[str, JsonValue], ...]


class Entity(Protocol):
    @property
    def name(self) -> str: ...
    async def act(self, spec: ActionSpec) -> EntityAction: ...
    async def observe(self, event: Event) -> None: ...
    def snapshot(self) -> EntitySnapshot: ...
    def restore(self, snap: EntitySnapshot) -> None: ...


class ComposedEntity:
    def __init__(
        self,
        name: str,
        components: tuple[Component, ...],
        act_component: ActComponent,
    ) -> None:
        seen: set[str] = set()
        for component in components:
            if component.name in seen:
                raise SnapshotError(f"duplicate component name {component.name!r}")
            seen.add(component.name)
        self._name = name
        self._components = components
        self._act_component = act_component
        self._phase: Phase = "READY"

    @property
    def name(self) -> str:
        return self._name

    def get_component(self, name: str) -> Component:
        for component in self._components:
            if component.name == name:
                return component
        raise KeyError(name)

    def _enter(self, phase: Phase) -> None:
        check_successor(self._phase, phase)
        self._phase = phase

    async def act(self, spec: ActionSpec) -> EntityAction:
        self._enter("PRE_ACT")
        maybe_blocks = await asyncio.gather(
            *(component.pre_act(spec) for component in self._components)
        )
        blocks = tuple(block for block in maybe_blocks if block is not None)
        action = await self._act_component.get_action_attempt(blocks, spec)
        self._enter("POST_ACT")
        await asyncio.gather(
            *(component.post_act(action) for component in self._components)
        )
        self._enter("UPDATE")
        await asyncio.gather(*(component.update() for component in self._components))
        self._phase = "READY"
        return action

    async def observe(self, event: Event) -> None:
        self._enter("PRE_OBSERVE")
        await asyncio.gather(
            *(component.pre_observe(event) for component in self._components)
        )
        self._enter("POST_OBSERVE")
        await asyncio.gather(
            *(component.post_observe() for component in self._components)
        )
        self._enter("UPDATE")
        await asyncio.gather(*(component.update() for component in self._components))
        self._phase = "READY"

    # Acting components are not in _components, but a stateful one (an LM
    # call counter, for instance) must survive a resume; it snapshots under
    # this reserved name.
    _ACT_STATE = "__act__"

    def _act_is_stateful(self) -> bool:
        act = self._act_component
        return hasattr(act, "state_model") and hasattr(act, "get_state")

    def snapshot(self) -> EntitySnapshot:
        entries = [
            (component.name, component.get_state().model_dump(mode="json"))
            for component in sorted(self._components, key=lambda c: c.name)
        ]
        if self._act_is_stateful():
            act_state = self._act_component.get_state().model_dump(mode="json")
            entries.append((self._ACT_STATE, act_state))
        return EntitySnapshot(entity=self._name, components=tuple(entries))

    def restore(self, snap: EntitySnapshot) -> None:
        if snap.entity != self._name:
            raise SnapshotError(
                f"snapshot is for {snap.entity!r}, entity is {self._name!r}"
            )
        act_entries = [raw for name, raw in snap.components if name == self._ACT_STATE]
        component_entries = [
            (name, raw) for name, raw in snap.components if name != self._ACT_STATE
        ]
        if self._act_is_stateful() != bool(act_entries):
            raise SnapshotError(
                "acting-component state mismatch: entity and snapshot disagree "
                "on whether the act component carries state"
            )
        own_names = {component.name for component in self._components}
        snap_names = {name for name, _ in component_entries}
        if own_names != snap_names:
            raise SnapshotError(
                f"component mismatch: entity has {sorted(own_names)}, "
                f"snapshot has {sorted(snap_names)}"
            )
        for name, raw_state in component_entries:
            component = self.get_component(name)
            try:
                state = component.state_model.model_validate(raw_state)
            except ValidationError as error:
                raise SnapshotError(
                    f"state for component {name!r} failed validation: {error}"
                ) from error
            component.set_state(state)
        for raw_state in act_entries:
            act = self._act_component
            try:
                state = act.state_model.model_validate(raw_state)
            except ValidationError as error:
                raise SnapshotError(
                    f"acting-component state failed validation: {error}"
                ) from error
            act.set_state(state)

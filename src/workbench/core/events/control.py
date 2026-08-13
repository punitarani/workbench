"""Simulation-control payloads. Tagged ``sim.*``: offstage, never projected."""

from typing import Literal

from pydantic import Field

from workbench.core.events._base import Payload


class SimRunStartedPayload(Payload):
    kind: Literal["sim.run.started"]
    run_id: str
    seed_root: int = Field(ge=0, lt=2**64)
    workplace_id: str
    config_hash: str
    schema_version: int
    epoch: str
    timezone: str


class SimDayStartedPayload(Payload):
    kind: Literal["sim.day.started"]
    day: str


class SimDayEndedPayload(Payload):
    kind: Literal["sim.day.ended"]
    day: str


class SimGmNotePayload(Payload):
    kind: Literal["sim.gm.note"]
    note: str
    rejected_intent: str | None = None
    # The entity whose action the note concerns; when set, the note routes
    # back to that entity so agents can correct instead of repeating.
    entity: str | None = None


class SimCuePayload(Payload):
    """A nudge to an external actor: something in their world moved and
    they are about to bring the firm work. The note is the situation;
    the actor's model authors the actual message."""

    kind: Literal["sim.cue"]
    entity: str
    note: str
    topic: str = "general"


class SimPlanningPayload(Payload):
    """A morning planning turn for one entity, minted by the day chain at
    the day's first grid tick."""

    kind: Literal["sim.planning"]
    entity: str
    day: str


class SimReflectionPayload(Payload):
    """A scheduled reflection turn for one entity, minted by the day
    chain near end-of-day; every fifth workday widens to a weekly scope."""

    kind: Literal["sim.reflection"]
    entity: str
    day: str
    scope: Literal["daily", "weekly"] = "daily"


class SimCheckpointPayload(Payload):
    kind: Literal["sim.checkpoint"]
    step: int = Field(ge=0)


class SimWakePayload(Payload):
    """A scheduled check-in turn for one simulated persona. Offstage."""

    kind: Literal["sim.wake"]
    entity: str

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


class SimCheckpointPayload(Payload):
    kind: Literal["sim.checkpoint"]
    step: int = Field(ge=0)


class SimWakePayload(Payload):
    """A scheduled check-in turn for one simulated persona. Offstage."""

    kind: Literal["sim.wake"]
    entity: str

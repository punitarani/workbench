"""Snapshots that actually resume.

The snapshot embeds the config hash and the engine's exact position; resume
validates both strictly. Nothing is silently dropped, nothing restarts.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from workbench.core.worldlog import read_events
from workbench.simulation.engine.attention import AttentionBookState
from workbench.simulation.engine.queue import ScheduledEvent
from workbench.simulation.entity.entity import EntitySnapshot
from workbench.simulation.errors import ConfigMismatchError, SnapshotError
from workbench.simulation.time_model import TimeModelState


class EngineState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: int = Field(ge=0)
    next_seq: int = Field(ge=0)
    next_order: int = Field(ge=0)
    time: TimeModelState
    queue: tuple[ScheduledEvent, ...]
    attention: AttentionBookState
    entities: tuple[EntitySnapshot, ...]
    game_master: JsonValue


class SimulationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    config_hash: str
    seed_root: int = Field(ge=0, lt=2**64)
    world_log_length: int = Field(ge=0)
    engine: EngineState


def save_snapshot(snapshot: SimulationSnapshot, path: Path) -> None:
    path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_snapshot(path: Path) -> SimulationSnapshot:
    try:
        return SimulationSnapshot.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except ValidationError as error:
        raise SnapshotError(f"snapshot {path} failed validation: {error}") from error


def verify_resume(
    snapshot: SimulationSnapshot, *, config_hash: str, log_path: Path
) -> None:
    if snapshot.config_hash != config_hash:
        raise ConfigMismatchError(
            f"snapshot was taken under config {snapshot.config_hash}, "
            f"resume is running config {config_hash}"
        )
    actual_length = len(read_events(log_path))
    if actual_length != snapshot.world_log_length:
        raise SnapshotError(
            f"world log has {actual_length} events, "
            f"snapshot expects {snapshot.world_log_length}"
        )

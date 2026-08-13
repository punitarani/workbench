"""Seeded cue schedules for external actors."""

from collections.abc import Callable, Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.seed import Seed, derive_rng


class CueDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    note: str
    topic: str = "general"
    # Seconds after midnight of the cue's day.
    at: int = Field(ge=0, lt=86_400)


class DirectorSchedule(Protocol):
    def cues_for(self, day: str) -> tuple[CueDraft, ...]: ...


class ClientProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    # Expected cues per workday, in thousandths (450 = 0.45/day).
    rate_millis: int = Field(ge=0)
    # (note template, topic) pools the schedule draws situations from.
    situations: tuple[tuple[str, str], ...] = Field(min_length=1)


class PoissonCueSchedule:
    """Quasi-Poisson arrivals on the day's grid ticks: each client's rate
    (optionally scaled by a season function) becomes zero or more cues at
    seeded times inside working hours."""

    def __init__(
        self,
        *,
        seed: Seed,
        clients: tuple[ClientProfile, ...],
        season: Callable[[str], Mapping[str, int]] | None = None,
        day_start: int = 9 * 3600,
        day_end: int = 16 * 3600,
        grid_seconds: int = 1800,
        max_cues_per_day: int = 8,
    ) -> None:
        self._seed = seed
        self._clients = clients
        self._season = season
        self._day_start = day_start
        self._day_end = day_end
        self._grid = grid_seconds
        self._max_cues = max_cues_per_day

    def cues_for(self, day: str) -> tuple[CueDraft, ...]:
        season_multipliers: Mapping[str, int] = (
            self._season(day) if self._season is not None else {}
        )
        cues: list[CueDraft] = []
        for profile in self._clients:
            rng = derive_rng(self._seed, "director.cues", day, profile.entity)
            multiplier = season_multipliers.get(profile.entity, 1000)
            mean = profile.rate_millis * multiplier / 1_000_000
            count = int(mean) + (1 if rng.random() < mean - int(mean) else 0)
            for _ in range(count):
                ticks = (self._day_end - self._day_start) // self._grid
                at = self._day_start + rng.randrange(0, max(1, ticks)) * self._grid
                note, topic = profile.situations[
                    rng.randrange(0, len(profile.situations))
                ]
                cues.append(
                    CueDraft(entity=profile.entity, note=note, topic=topic, at=at)
                )
        cues.sort(key=lambda cue: (cue.at, cue.entity))
        # The damper: a day never carries more inbound than the cap, so
        # traffic cannot snowball past what the firm can absorb.
        return tuple(cues[: self._max_cues])

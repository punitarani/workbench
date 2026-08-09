"""Pluggable simulated time.

``EventDrivenTimeModel`` skips dead air: waiting costs nothing, only the
event queue moves the clock. A wall-clock implementation of the same
protocol is the seam for future online, real-time operation.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.simtime import SimTime
from workbench.simulation.errors import TimeError


class TimeModelState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    now: int = Field(ge=0)


class TimeModel(Protocol):
    def now(self) -> SimTime: ...
    def advance_to(self, t: SimTime) -> None: ...
    async def wait_until(self, t: SimTime) -> None: ...
    def get_state(self) -> TimeModelState: ...
    def set_state(self, state: TimeModelState) -> None: ...


class EventDrivenTimeModel:
    def __init__(self, *, now: SimTime) -> None:
        self._now = now

    def now(self) -> SimTime:
        return self._now

    def advance_to(self, t: SimTime) -> None:
        if int(t) < int(self._now):
            raise TimeError(f"cannot advance from {int(self._now)} back to {int(t)}")
        self._now = t

    async def wait_until(self, t: SimTime) -> None:
        return None

    def get_state(self) -> TimeModelState:
        return TimeModelState(now=int(self._now))

    def set_state(self, state: TimeModelState) -> None:
        self._now = SimTime(state.now)

"""Entity wake-up timers, fired in (fires_at, entity, timer_id) order."""

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.simtime import SimTime


class EntityTimer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    timer_id: str
    fires_at: int = Field(ge=0)
    note: str = ""


class TimerBookState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timers: tuple[EntityTimer, ...] = ()


class TimerBook:
    def __init__(self) -> None:
        self._timers: list[EntityTimer] = []

    def schedule(self, timer: EntityTimer) -> None:
        self._timers.append(timer)

    def due(self, now: SimTime) -> tuple[EntityTimer, ...]:
        fired = sorted(
            (t for t in self._timers if t.fires_at <= int(now)),
            key=lambda t: (t.fires_at, t.entity, t.timer_id),
        )
        self._timers = [t for t in self._timers if t.fires_at > int(now)]
        return tuple(fired)

    def get_state(self) -> TimerBookState:
        return TimerBookState(
            timers=tuple(
                sorted(
                    self._timers, key=lambda t: (t.fires_at, t.entity, t.timer_id)
                )
            )
        )

    def set_state(self, state: TimerBookState) -> None:
        self._timers = list(state.timers)

"""Calendar arithmetic for multi-day chronicles.

Dates come only from explicit ISO strings; nothing here reads a clock. A day
index offsets from the window's start date, and simulated time for day N
starts at exactly N * 86400 seconds — flat day arithmetic, no DST steps.
Wall-clock rendering happens only through the timezone-aware epoch.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator

from workbench.core.simtime import SimDuration
from workbench.simulation.errors import ChronicleError

SECONDS_PER_DAY = 86_400


class CalendarWindow(BaseModel):
    """An inclusive run of calendar days addressed by zero-based day index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_date: str
    end_date: str
    timezone: str

    @model_validator(mode="after")
    def _well_formed(self) -> CalendarWindow:
        if self._end < self._start:
            raise ValueError(
                f"end_date {self.end_date} precedes start_date {self.start_date}"
            )
        ZoneInfo(self.timezone)
        return self

    @property
    def _start(self) -> date:
        return date.fromisoformat(self.start_date)

    @property
    def _end(self) -> date:
        return date.fromisoformat(self.end_date)

    @property
    def day_count(self) -> int:
        return (self._end - self._start).days + 1

    def _check_index(self, day_index: int) -> None:
        if not 0 <= day_index < self.day_count:
            raise ChronicleError(
                f"day index {day_index} outside window "
                f"{self.start_date}..{self.end_date} ({self.day_count} days)"
            )

    def date_of(self, day_index: int) -> date:
        self._check_index(day_index)
        return self._start + timedelta(days=day_index)

    def iso_date(self, day_index: int) -> str:
        return self.date_of(day_index).isoformat()

    def day_offset(self, day_index: int) -> SimDuration:
        self._check_index(day_index)
        return SimDuration(day_index * SECONDS_PER_DAY)

    def is_workday(self, day_index: int) -> bool:
        return self.date_of(day_index).weekday() < 5

    def workdays(self) -> tuple[int, ...]:
        return tuple(index for index in range(self.day_count) if self.is_workday(index))

    def epoch(self) -> datetime:
        start = self._start
        return datetime(
            start.year, start.month, start.day, tzinfo=ZoneInfo(self.timezone)
        )

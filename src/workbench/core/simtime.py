"""Simulated time: integer seconds since the scenario epoch.

Integer arithmetic keeps every timestamp byte-stable; calendar rendering
happens only through an explicit timezone-aware epoch.
"""

from datetime import datetime, timedelta
from typing import NewType

SimTime = NewType("SimTime", int)
SimDuration = NewType("SimDuration", int)


def _require_aware(epoch: datetime) -> None:
    if epoch.tzinfo is None:
        raise ValueError("epoch must be timezone-aware")


def to_datetime(t: SimTime, *, epoch: datetime) -> datetime:
    _require_aware(epoch)
    return epoch + timedelta(seconds=int(t))


def from_datetime(moment: datetime, *, epoch: datetime) -> SimTime:
    _require_aware(epoch)
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    seconds = (moment - epoch).total_seconds()
    if seconds < 0:
        raise ValueError(
            f"moment {moment.isoformat()} precedes epoch {epoch.isoformat()}"
        )
    if seconds != int(seconds):
        raise ValueError("sub-second precision is not representable in SimTime")
    return SimTime(int(seconds))

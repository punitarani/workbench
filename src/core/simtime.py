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


# --- is this integer actually simulated time? -----------------------------
#
# A `SimTime` is seconds from the run's epoch, and nothing in the type stops
# a different unit being written into one. Two wrong units turned up in a
# single field of one recorded calendar: a wall-clock time of day that had
# lost its date, and an absolute Unix timestamp. Neither raises. Each is a
# plausible integer that projects into a plausible row, and the result is a
# diary holding meetings before the organization opened and meetings in 2081.
#
# **The test cannot be on the value alone.** With a midnight epoch, `31500`
# is both "08:45 on the first day", which is perfectly legitimate, and the
# shape a lost wall-clock time takes. Judging by magnitude quarantines real
# events: of 48 such starts in one world, 8 were genuine first-day meetings.
# The first version of this rule did exactly that, and "verified" it by
# filtering with the same threshold that defined the fault -- a check that
# could only ever agree with itself.
#
# So the discriminators are causal and structural instead:
#
#   * a start *earlier than the moment the event was recorded* is scheduled
#     into the past, which no real calendar entry is;
#   * a start beyond any horizon the run could reach is a different clock.
#
# This lives in `core` because two components must agree on it -- the
# projection that drops corrupt rows and the gate that reports them -- and a
# rule two components must agree on belongs to neither.

# Generous on purpose. A litigation calendar legitimately holds dates years
# out, so this only has to exclude a different clock: an absolute Unix
# timestamp is ~1.7e9, while ten years of simulated seconds is ~3.2e8.
FAR_FUTURE = 10 * 365 * 86_400


def misread_unit(
    start: int, recorded_at: int, *, horizon: int = FAR_FUTURE
) -> str | None:
    """Why `start` cannot be simulated time, or None when it is fine.

    `recorded_at` is the simulated moment the scheduling event itself was
    written. Passing it is what makes this non-circular: it comes from the
    log's own ordering rather than from the value under suspicion.
    """

    if start < 0:
        return "negative"
    if start < recorded_at:
        return "scheduled-into-the-past"
    if start > horizon:
        return "beyond-any-run-horizon"
    return None

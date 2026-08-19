from datetime import UTC, datetime, timedelta

import pytest

from core.simtime import SimTime, from_datetime, to_datetime

EPOCH = datetime(2026, 3, 12, 0, 0, tzinfo=UTC)


def test_round_trip() -> None:
    moment = EPOCH + timedelta(hours=9, minutes=40)
    t = from_datetime(moment, epoch=EPOCH)
    assert t == SimTime(9 * 3600 + 40 * 60)
    assert to_datetime(t, epoch=EPOCH) == moment


def test_before_epoch_rejected() -> None:
    with pytest.raises(ValueError):
        from_datetime(EPOCH - timedelta(seconds=1), epoch=EPOCH)


def test_naive_epoch_rejected() -> None:
    with pytest.raises(ValueError):
        from_datetime(datetime(2026, 3, 12, 9, 0), epoch=datetime(2026, 3, 12))

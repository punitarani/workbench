import pydantic
import pytest
from payload_samples import sample_payloads

from workbench.core.events import (
    SCHEMA_VERSION,
    TAG_REGISTRY,
    Event,
    EventDraft,
)


def make_event(seq: int = 0, **overrides) -> Event:
    payload = sample_payloads()["chat.message"]
    defaults = dict(
        seq=seq,
        time=1000,
        tag=payload.kind,
        source="daniel",
        caused_by=None,
        payload=payload,
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_schema_version() -> None:
    assert SCHEMA_VERSION == 1


def test_every_payload_round_trips_byte_stable() -> None:
    for kind, payload in sample_payloads().items():
        event = Event(seq=0, time=0, tag=kind, source="gm", payload=payload)
        dumped = event.model_dump_json()
        assert Event.model_validate_json(dumped).model_dump_json() == dumped


def test_registry_matches_samples_exactly() -> None:
    assert set(TAG_REGISTRY) == set(sample_payloads())
    for kind, cls in TAG_REGISTRY.items():
        assert type(sample_payloads()[kind]) is cls


def test_event_id_is_derived_from_seq() -> None:
    assert make_event(seq=42).event_id == "evt-000042"
    with pytest.raises(pydantic.ValidationError):
        make_event(seq=42, event_id="evt-000041")


def test_tag_must_match_payload_kind() -> None:
    with pytest.raises(pydantic.ValidationError):
        make_event(tag="email.message")


def test_events_are_frozen_and_forbid_extras() -> None:
    event = make_event()
    with pytest.raises(pydantic.ValidationError):
        event.seq = 5
    with pytest.raises(pydantic.ValidationError):
        make_event(unknown_field=1)


def test_sort_key_orders_by_time_then_seq() -> None:
    early = make_event(seq=5, time=100)
    late_same_time = make_event(seq=6, time=100)
    later = make_event(seq=1, time=200)
    ordered = sorted([later, late_same_time, early], key=lambda e: e.sort_key())
    assert ordered == [early, late_same_time, later]


def test_draft_carries_no_seq_or_time_authority() -> None:
    draft = EventDraft(
        tag="chat.message",
        source="daniel",
        payload=sample_payloads()["chat.message"],
        delay=60,
    )
    assert draft.delay == 60
    assert not hasattr(draft, "seq")


def test_time_entries_carry_money() -> None:
    entry = sample_payloads()["work.time.logged"]
    assert entry.rate_cents == 44_500 and entry.billable
    assert entry.amount_cents == 66_750, "90 minutes at $445/hr"
    written_off = entry.model_copy(update={"billable": False})
    assert written_off.amount_cents is None, "a write-off charges nothing"
    tracked = entry.model_copy(update={"rate_cents": None})
    assert tracked.amount_cents is None, "unrated time has no amount"

import random

import pytest

from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload
from workbench.core.simtime import SimTime
from workbench.simulation.engine.queue import EventQueue
from workbench.simulation.errors import TimeError
from workbench.simulation.time_model import EventDrivenTimeModel


def chat_event(seq: int, time: int) -> Event:
    payload = ChatMessagePayload(
        kind="chat.message",
        chat_message_id=f"chm-{seq:06d}",
        conversation_id="cnv-000001",
        reply_to=None,
        sender="per-x",
        body="hi",
    )
    return Event(seq=seq, time=time, tag=payload.kind, source="gm", payload=payload)


def test_queue_pops_in_time_then_seq_order() -> None:
    events = [chat_event(seq=i, time=(i * 37) % 5 * 100) for i in range(50)]
    shuffled = events[:]
    random.Random(7).shuffle(shuffled)
    queue = EventQueue()
    for event in shuffled:
        queue.push(event)
    popped = [queue.pop() for _ in range(len(events))]
    assert popped == sorted(events, key=lambda e: e.sort_key())


def test_queue_peek_and_len() -> None:
    queue = EventQueue()
    assert len(queue) == 0
    queue.push(chat_event(seq=1, time=200))
    queue.push(chat_event(seq=0, time=100))
    assert len(queue) == 2
    assert queue.peek().seq == 0
    assert len(queue) == 2


def test_queue_snapshot_is_sorted() -> None:
    queue = EventQueue()
    queue.push(chat_event(seq=2, time=300))
    queue.push(chat_event(seq=0, time=100))
    queue.push(chat_event(seq=1, time=100))
    assert [e.seq for e in queue.snapshot()] == [0, 1, 2]


def test_pop_empty_raises() -> None:
    with pytest.raises(IndexError):
        EventQueue().pop()


async def test_time_model_advances_and_waits_instantly() -> None:
    model = EventDrivenTimeModel(now=SimTime(0))
    await model.wait_until(SimTime(5000))
    model.advance_to(SimTime(5000))
    assert model.now() == 5000


def test_time_model_rejects_regression() -> None:
    model = EventDrivenTimeModel(now=SimTime(100))
    with pytest.raises(TimeError):
        model.advance_to(SimTime(50))


def test_time_model_state_round_trip() -> None:
    model = EventDrivenTimeModel(now=SimTime(0))
    model.advance_to(SimTime(777))
    state = model.get_state()
    fresh = EventDrivenTimeModel(now=SimTime(0))
    fresh.set_state(state)
    assert fresh.now() == 777

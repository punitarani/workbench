from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.simtime import SimTime
from workbench.simulation.engine.attention import AttentionBook, matches_prefix
from workbench.simulation.engine.timers import EntityTimer, TimerBook


def chat(seq: int, conversation: str = "cnv-dm-1") -> Event:
    payload = ChatMessagePayload(
        kind="chat.message",
        chat_message_id=f"chm-{seq:06d}",
        conversation_id=conversation,
        reply_to=None,
        sender="per-x",
        body="ping",
    )
    return Event(seq=seq, time=0, tag=payload.kind, source="gm", payload=payload)


def email(seq: int) -> Event:
    payload = EmailMessagePayload(
        kind="email.message",
        message_id=f"msg-{seq:06d}",
        thread_id="thr-000001",
        in_reply_to=None,
        sender="per-x",
        to=("per-y",),
        cc=(),
        subject="s",
        body="b",
        attachments=(),
    )
    return Event(seq=seq, time=0, tag=payload.kind, source="gm", payload=payload)


def test_prefix_matching_is_segment_wise() -> None:
    assert matches_prefix("email", "email.message")
    assert matches_prefix("email.message", "email.message")
    assert matches_prefix("chat", "chat.conversation.created")
    assert not matches_prefix("email.mess", "email.message")
    assert not matches_prefix("chat.message", "chat")
    assert not matches_prefix("ticket", "email.message")


def test_open_entities_receive_everything() -> None:
    book = AttentionBook(entities=("daniel",))
    assert book.should_deliver("daniel", email(1), now=SimTime(0))


def test_heads_down_defers_and_allows_breakthrough() -> None:
    book = AttentionBook(entities=("daniel",))
    book.set_heads_down("daniel", until=SimTime(5400), allow=("chat",))
    assert not book.should_deliver("daniel", email(1), now=SimTime(100))
    book.defer("daniel", email(1))
    assert book.should_deliver("daniel", chat(2), now=SimTime(100))


def test_heads_down_expires() -> None:
    book = AttentionBook(entities=("daniel",))
    book.set_heads_down("daniel", until=SimTime(5400), allow=())
    assert book.should_deliver("daniel", email(1), now=SimTime(5400))


def test_flush_returns_deferred_in_order_and_clears() -> None:
    book = AttentionBook(entities=("daniel",))
    book.set_heads_down("daniel", until=SimTime(5400), allow=())
    book.defer("daniel", email(1))
    book.defer("daniel", email(2))
    flushed = book.flush("daniel")
    assert [e.seq for e in flushed] == [1, 2]
    assert book.flush("daniel") == ()


def test_attention_state_round_trip() -> None:
    book = AttentionBook(entities=("daniel", "tom"))
    book.set_heads_down("daniel", until=SimTime(5400), allow=("chat",))
    book.defer("daniel", email(1))
    state = book.get_state()
    fresh = AttentionBook(entities=("daniel", "tom"))
    fresh.set_state(state)
    assert not fresh.should_deliver("daniel", email(2), now=SimTime(100))
    assert [e.seq for e in fresh.flush("daniel")] == [1]


def test_timers_fire_in_deterministic_order() -> None:
    book = TimerBook()
    book.schedule(
        EntityTimer(entity="tom", timer_id="check-email", fires_at=SimTime(300))
    )
    book.schedule(EntityTimer(entity="ann", timer_id="standup", fires_at=SimTime(300)))
    book.schedule(EntityTimer(entity="tom", timer_id="lunch", fires_at=SimTime(100)))
    assert [t.timer_id for t in book.due(SimTime(300))] == [
        "lunch",
        "standup",
        "check-email",
    ]
    assert book.due(SimTime(10_000)) == ()


def test_timer_state_round_trip() -> None:
    book = TimerBook()
    book.schedule(EntityTimer(entity="tom", timer_id="x", fires_at=SimTime(100)))
    fresh = TimerBook()
    fresh.set_state(book.get_state())
    assert [t.timer_id for t in fresh.due(SimTime(100))] == ["x"]


def test_flushable_only_when_expired_with_deferred() -> None:
    book = AttentionBook(entities=("daniel",))
    assert not book.flushable("daniel", now=SimTime(0))
    book.set_heads_down("daniel", until=SimTime(500), allow=())
    book.defer("daniel", email(1))
    assert not book.flushable("daniel", now=SimTime(100))
    assert book.flushable("daniel", now=SimTime(500))

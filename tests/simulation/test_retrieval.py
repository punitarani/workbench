"""Retrieval scoring: deterministic scaled integers, ref overlap
dominant, ties broken by recency then ref."""

from simulation.persona.memory_stream import MemoryRecord
from simulation.persona.retrieval import (
    RetrievalQuery,
    render_memories,
    retrieve,
    score,
    tokens_of,
)

NOW = 60 * 86_400


def _record(
    ref: str, *, time: int, importance: int, gist: str, refs=()
) -> MemoryRecord:
    return MemoryRecord(
        ref=ref,
        kind="observation",
        time=time,
        importance=importance,
        gist=gist,
        refs=frozenset(refs),
    )


def test_ref_overlap_dominates_token_overlap() -> None:
    query = RetrievalQuery(
        refs=frozenset({"thr-000001"}), tokens=tokens_of("vantage nda term")
    )
    on_thread = _record(
        "evt-1",
        time=NOW - 3600,
        importance=5,
        gist="Reply landed",
        refs={"thr-000001"},
    )
    wordy = _record(
        "evt-2",
        time=NOW - 3600,
        importance=5,
        gist="vantage nda term chatter elsewhere",
    )
    assert score(on_thread, query, now=NOW) > score(wordy, query, now=NOW)


def test_recency_buckets_decay() -> None:
    query = RetrievalQuery()
    fresh = _record("evt-1", time=NOW - 600, importance=5, gist="x")
    stale = _record("evt-2", time=NOW - 40 * 86_400, importance=5, gist="x")
    assert score(fresh, query, now=NOW) == 5 * 8
    assert score(stale, query, now=NOW) == 5 * 1


def test_retrieve_orders_and_caps_deterministically() -> None:
    query = RetrievalQuery(refs=frozenset({"tkt-000009"}))
    records = tuple(
        _record(
            f"evt-{index}",
            time=NOW - index * 3600,
            importance=3 + (index % 5),
            gist=f"record {index}",
            refs={"tkt-000009"} if index % 2 == 0 else (),
        )
        for index in range(30)
    )
    first = retrieve(records, query, now=NOW, k=5)
    second = retrieve(tuple(reversed(records)), query, now=NOW, k=5)
    assert first == second, "input order never changes the ranking"
    assert len(first) == 5
    assert all("tkt-000009" in record.refs for record in first)


def test_render_is_compact_and_dated() -> None:
    records = (
        _record("evt-1", time=NOW - 600, importance=9, gist="Boss asked for the memo"),
        _record("evt-2", time=NOW - 2 * 86_400, importance=4, gist="Filed the rec"),
    )
    rendered = render_memories(records, now=NOW)
    assert "[today | !9] Boss asked for the memo" in rendered
    assert "[2d ago | !4] Filed the rec" in rendered
    assert render_memories((), now=NOW) == "None yet."

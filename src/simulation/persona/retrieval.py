"""Deterministic memory retrieval: importance × recency × relevance.

No embeddings and no floats — the world is typed, so relevance is ref
overlap plus a light token overlap, recency is bucketed, and every score
is a scaled integer. The same records and query always produce the same
ranking on every platform, which is what keeps replay byte-identical.
"""

import re

from pydantic import BaseModel, ConfigDict

from simulation.persona.memory_stream import MemoryRecord

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")

DEFAULT_K = 12


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    refs: frozenset[str] = frozenset()
    tokens: frozenset[str] = frozenset()


def tokens_of(*texts: str) -> frozenset[str]:
    found: set[str] = set()
    for text in texts:
        found.update(_TOKEN_PATTERN.findall(text.casefold()))
    return frozenset(found)


def _recency_bucket(age_seconds: int) -> int:
    if age_seconds < 2 * 3600:
        return 8
    if age_seconds < 86_400:
        return 6
    if age_seconds < 3 * 86_400:
        return 4
    if age_seconds < 7 * 86_400:
        return 3
    if age_seconds < 30 * 86_400:
        return 2
    return 1


def score(record: MemoryRecord, query: RetrievalQuery, *, now: int) -> int:
    recency = _recency_bucket(max(0, now - record.time))
    ref_overlap = len(record.refs & query.refs)
    token_overlap = min(4, len(tokens_of(record.gist) & query.tokens))
    # A typed-ref match is a certainty the token heuristic never is: one
    # shared ref outranks even the maximum token overlap.
    relevance = 5 * ref_overlap + token_overlap
    return record.importance * recency * (1 + relevance)


def retrieve(
    records: tuple[MemoryRecord, ...],
    query: RetrievalQuery,
    *,
    now: int,
    k: int = DEFAULT_K,
) -> tuple[MemoryRecord, ...]:
    """Top-k by score; ties break to the newer record, then the ref —
    a total, stable, deterministic order."""

    ranked = sorted(
        records,
        key=lambda record: (
            -score(record, query, now=now),
            -record.time,
            record.ref,
        ),
    )
    return tuple(ranked[:k])


def render_memories(records: tuple[MemoryRecord, ...], *, now: int) -> str:
    """The 'relevant memories' prompt block: one line per record."""

    if not records:
        return "None yet."
    lines = []
    for record in records:
        age_days = max(0, now - record.time) // 86_400
        when = "today" if age_days == 0 else f"{age_days}d ago"
        lines.append(f"- [{when} | !{record.importance}] {record.gist}")
    return "\n".join(lines)

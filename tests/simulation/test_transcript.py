from simulation.entity.context import ContextBlock
from simulation.transcript import TranscriptEntry, TranscriptStore


def entry(text: str = "content") -> TranscriptEntry:
    return TranscriptEntry(
        entity="daniel",
        phase="PRE_ACT",
        blocks=(
            ContextBlock(label="Identity", content=text),
            ContextBlock(label="Debug", content="internal", debug_only=True),
        ),
        note="",
    )


def test_identical_entries_dedup() -> None:
    store = TranscriptStore()
    first = store.add(entry())
    second = store.add(entry())
    assert first == second
    assert len(store.entries()) == 1


def test_distinct_entries_are_kept() -> None:
    store = TranscriptStore()
    store.add(entry("a"))
    store.add(entry("b"))
    assert len(store.entries()) == 2


def test_entry_hash_is_content_derived() -> None:
    assert TranscriptStore().add(entry()) == TranscriptStore().add(entry())

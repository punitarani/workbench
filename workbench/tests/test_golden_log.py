"""Serialization drift guard: the fixture log must match its committed bytes.

A failure here means Event serialization changed — which invalidates every
recorded world log and cassette. That is sometimes intentional; regenerate
with `uv run python workbench/tests/generate_golden.py` and say so in the
commit message.
"""

from pathlib import Path

from worldlog_fixtures import coherent_events

GOLDEN = Path(__file__).parent / "golden" / "world.jsonl"


def fixture_bytes() -> bytes:
    return b"".join(
        event.model_dump_json().encode("utf-8") + b"\n" for event in coherent_events()
    )


def test_fixture_serialization_matches_golden() -> None:
    assert GOLDEN.exists(), "golden missing; run workbench/tests/generate_golden.py"
    assert fixture_bytes() == GOLDEN.read_bytes()

"""Structural acceptance for the legal workplace: everything that must hold
before any model is ever called."""

from core.seed import Seed
from core.worldlog import validate_events
from simulation.workplace.compile import compile_workplace
from workplaces.legal import (
    STANDARD_ARTIFACT_MARKERS,
    UNWRITTEN_STANDARD_PHRASES,
    WORKPLACE,
)


def test_workplace_compiles_and_genesis_validates() -> None:
    compiled = compile_workplace(WORKPLACE, Seed(root=42))
    report = validate_events(compiled.genesis)
    assert report.ok, report.findings
    assert len(compiled.personas) == 5, "five internal simulated people"


def test_cast_and_channels() -> None:
    people = {p.person_id: p for p in WORKPLACE.people}
    assert people["per-ravi-deshmukh"].persona is None, "external counsel is scripted"
    assert people["per-daniel-reyes"].persona is not None
    channel_names = {c.name for c in WORKPLACE.channels}
    assert "#legal" in channel_names


def test_daniel_holds_the_unwritten_standard() -> None:
    daniel = next(p for p in WORKPLACE.people if p.person_id == "per-daniel-reyes")
    topics = {item.topic: item for item in daniel.persona.knowledge}
    standard = topics["vendor NDA standard"]
    assert standard.share_policy == "if_asked"
    for phrase in UNWRITTEN_STANDARD_PHRASES:
        assert phrase.casefold() in standard.content.casefold()


def test_unwritten_standard_litmus_precondition() -> None:
    """The standard must appear in NO seed document and NO day-script body."""
    haystacks = [d.content for d in WORKPLACE.seed_documents]
    haystacks += [a.body for a in WORKPLACE.day_script]
    haystacks += [a.attachment.content for a in WORKPLACE.day_script if a.attachment]
    for phrase in (*UNWRITTEN_STANDARD_PHRASES, *STANDARD_ARTIFACT_MARKERS):
        for haystack in haystacks:
            assert phrase.casefold() not in haystack.casefold(), (
                f"standard phrase {phrase!r} leaked into seeded content"
            )


def test_playbook_has_the_deliberate_gap() -> None:
    playbook = next(d for d in WORKPLACE.seed_documents if "playbook" in d.path)
    assert "customer" in playbook.content.casefold()
    assert "vendor" not in playbook.content.casefold(), (
        "the playbook must not cover vendor NDAs; that knowledge lives only with Daniel"
    )


def test_day_script_delivers_the_nda() -> None:
    arrival = WORKPLACE.day_script[0]
    assert arrival.at == "09:40"
    assert arrival.attachment is not None
    assert "vantage" in arrival.attachment.path

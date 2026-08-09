"""Storyline acceptance: beats land on workdays, the full directed build
validates, and each arc leaves the evidence its tasks will mine — all
offline, with deterministic stand-in prose."""

import importlib.util
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.tickets import TicketCommentedPayload, TicketUpdatedPayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.errors import ConfigError
from workbench.workplaces.hartwell import WINDOW, build_genesis
from workbench.workplaces.hartwell.storylines import (
    ARROYO_HEARING_TITLE,
    CASCADIA_LETTER_TITLE,
    INDEMNITY_PARAGRAPH,
    IRONCLAD_NDA_TITLE,
    LEXIPOINT_NDA_TITLE,
    LUMEN_AGREEMENT_TITLE,
    NDA_RESIDUALS_CLAUSE,
    PLAYBOOK_TITLE,
    S2_TICKET,
    S4_CLOSED_DATE,
    S4_TICKET,
    StorylineDirector,
    author_content_offline,
    content_requests,
)


def _load_build_history() -> ModuleType:
    path = Path(__file__).parents[2] / "datasets" / "hartwell" / "build_history.py"
    spec = importlib.util.spec_from_file_location("hartwell_build_history", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_texts() -> dict[str, str]:
    return author_content_offline(
        lambda request: (
            f"[{request.name}] Deterministic stand-in prose for "
            "offline builds; the load-bearing facts live in code constants."
        )
    )


@pytest.fixture(scope="module")
def full_log(tmp_path_factory: pytest.TempPathFactory) -> list:
    module = _load_build_history()
    out = tmp_path_factory.mktemp("hartwell-full")
    log_path = module.build_world(
        out, Seed(root=42), day_count=None, texts=fake_texts()
    )
    return read_events(log_path)


def _versions_by_title(events: list) -> dict[str, dict[int, str]]:
    titles: dict[str, str] = {}
    versions: dict[str, dict[int, str]] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, DocumentCreatedPayload):
            titles[payload.document_id] = payload.title
            versions.setdefault(payload.title, {})[1] = payload.content
        elif isinstance(payload, DocumentRevisedPayload):
            versions[titles[payload.document_id]][payload.revision] = payload.content
    return versions


def _event_date(event) -> str:
    return WINDOW.iso_date(int(event.time) // 86_400)


def test_every_content_request_is_named_uniquely() -> None:
    names = [request.name for request in content_requests()]
    assert len(names) == len(set(names))
    assert all(request.prompt for request in content_requests())


def test_director_requires_complete_texts() -> None:
    genesis = build_genesis(Seed(root=42))
    with pytest.raises(ConfigError):
        StorylineDirector(genesis=genesis, texts={})


def test_beats_land_on_workdays_within_window() -> None:
    genesis = build_genesis(Seed(root=42))
    director = StorylineDirector(genesis=genesis, texts=fake_texts())
    workdays = {WINDOW.iso_date(index) for index in WINDOW.workdays()}
    assert director.dates, "the director scripts at least one beat"
    assert set(director.dates) <= workdays
    assert director.dates[0] >= WINDOW.start_date
    assert director.dates[-1] <= WINDOW.end_date


def test_full_build_validates_with_zero_findings(full_log: list) -> None:
    report = validate_events(full_log)
    assert report.findings == ()
    started = [event for event in full_log if event.tag == "sim.day.started"]
    assert len(started) == 87


def test_full_build_is_deterministic(tmp_path: Path) -> None:
    module = _load_build_history()
    texts = fake_texts()
    first = module.build_world(
        tmp_path / "a", Seed(root=42), day_count=None, texts=texts
    ).read_bytes()
    second = module.build_world(
        tmp_path / "b", Seed(root=42), day_count=None, texts=texts
    ).read_bytes()
    assert first == second


def test_s1_playbook_and_practice_diverge(full_log: list) -> None:
    docs = _versions_by_title(full_log)
    playbook = docs[PLAYBOOK_TITLE]
    lexipoint = docs[LEXIPOINT_NDA_TITLE]
    ironclad = docs[IRONCLAD_NDA_TITLE]

    assert set(playbook) == {1, 2, 3}, "playbook revised twice in March"
    for content in playbook.values():
        assert "three (3) years" in content
        assert "Reject any residual-knowledge clause" in content

    assert "three (3) years" in lexipoint[1]
    assert "five (5) years" in lexipoint[2]
    assert "five (5) years" in ironclad[1]
    assert NDA_RESIDUALS_CLAUSE not in ironclad[1]
    assert NDA_RESIDUALS_CLAUSE in ironclad[2]


def test_s2_fee_dispute_joins_activities_to_email_dates(full_log: list) -> None:
    spike = [
        event
        for event in full_log
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and (
            "diligence" in event.payload.note.lower()
            or "data room" in event.payload.note.lower()
        )
        and "2026-04-03" < _event_date(event) <= "2026-04-30"
    ]
    assert len(spike) >= 5
    assert sum(event.payload.minutes for event in spike) > 600

    notes = [
        event
        for event in full_log
        if isinstance(event.payload, TicketCommentedPayload)
        and event.payload.ticket_id == S2_TICKET
        and "s2.note.resolution" in event.payload.body
    ]
    assert len(notes) == 1 and _event_date(notes[0]) == "2026-05-15"


def test_s3_indemnity_drops_silently_in_v3(full_log: list) -> None:
    lumen = _versions_by_title(full_log)[LUMEN_AGREEMENT_TITLE]
    assert INDEMNITY_PARAGRAPH in lumen[1]
    assert INDEMNITY_PARAGRAPH in lumen[2]
    assert INDEMNITY_PARAGRAPH not in lumen[3]
    revision3 = next(
        event.payload
        for event in full_log
        if isinstance(event.payload, DocumentRevisedPayload)
        and event.payload.revision == 3
        and INDEMNITY_PARAGRAPH not in event.payload.content
        and "9.1" in event.payload.content
    )
    assert "indemn" not in revision3.change_summary.lower(), (
        "the drop hides behind an innocuous summary"
    )


def test_s4_souring_ends_in_closure_and_letter(full_log: list) -> None:
    reactions = Counter(
        event.payload.chat_message_id
        for event in full_log
        if isinstance(event.payload, ChatReactionAddedPayload)
    )
    # Procedural chatter cites the matter by its full label; the storyline
    # voice never does, which isolates the sentiment arc.
    arc = [
        reactions.get(event.payload.chat_message_id, 0)
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and ("Cascadia" in event.payload.body or "Hollis" in event.payload.body)
        and "Cascadia supplier dispute" not in event.payload.body
    ]
    assert len(arc) >= 5
    assert arc[0] == 3 and arc[-2:] == [0, 0], "reaction counts decline"

    closures = [
        event
        for event in full_log
        if isinstance(event.payload, TicketUpdatedPayload)
        and event.payload.ticket_id == S4_TICKET
    ]
    assert len(closures) == 1
    assert _event_date(closures[0]) == S4_CLOSED_DATE
    change = closures[0].payload.changes[0]
    assert (change.field, change.old, change.new) == ("status", "open", "closed")
    assert CASCADIA_LETTER_TITLE in _versions_by_title(full_log)

    late_time = [
        event
        for event in full_log
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S4_TICKET
        and _event_date(event) > S4_CLOSED_DATE
    ]
    assert late_time == [], "no procedural time lands on the closed matter"


def test_s5_operative_date_lives_only_in_the_last_correction(full_log: list) -> None:
    hearings = [
        event.payload
        for event in full_log
        if isinstance(event.payload, CalendarEventScheduledPayload)
        and ARROYO_HEARING_TITLE in event.payload.title
    ]
    scheduled_days = [
        WINDOW.iso_date(int(payload.start) // 86_400) for payload in hearings
    ]
    assert scheduled_days == ["2026-04-28", "2026-05-20", "2026-06-18"]

    corrections = [
        event
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and "June 25" in event.payload.body
    ]
    assert len(corrections) >= 1
    assert _event_date(corrections[0]) == "2026-06-11"
    assert "2026-06-25" not in scheduled_days

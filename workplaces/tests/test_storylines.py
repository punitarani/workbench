"""Storyline acceptance: beats land on workdays, the full directed build
validates, and each arc leaves the evidence its tasks will mine — all
offline, with deterministic stand-in prose."""

import importlib.util
import re
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
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import TicketCommentedPayload, TicketUpdatedPayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.errors import ConfigError
from workbench.workplaces.hartwell import WINDOW, build_genesis
from workbench.workplaces.hartwell.storylines import (
    ARROYO_HEARING_TITLE,
    CASCADIA_LETTER_TITLE,
    CONFORMING_NDA_TITLES,
    INDEMNITY_PARAGRAPH,
    IRONCLAD_NDA_TITLE,
    LEXIPOINT_NDA_TITLE,
    LUMEN_AGREEMENT_TITLE,
    LUMEN_SOW_TITLE,
    NDA_RESIDUALS_CLAUSE,
    PLAYBOOK_TITLE,
    S2_CUTOFF_CHAT,
    S2_SUPPORT_MARKERS,
    S2_TICKET,
    S4_CLOSED_DATE,
    S4_TICKET,
    S5_DM_CORRECTION,
    S5_RECAP_SUBJECT,
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
    assert len(started) == WINDOW.day_count == 121, (
        "the record covers every calendar day, weekends and holidays included"
    )


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

    nda_titles = {title for title in docs if title.startswith("Mutual NDA")}
    assert len(nda_titles) == 9, "the survey corpus holds nine vendor NDAs"
    for title in CONFORMING_NDA_TITLES:
        assert len(docs[title]) >= 2, f"{title} carries a revision history"
        for content in docs[title].values():
            assert "three (3) years" in content, "conforming NDAs hold"
            assert NDA_RESIDUALS_CLAUSE not in content

    chat_bodies = [
        event.payload.body
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
    ]
    assert any("carve-out LexiPoint" in body for body in chat_bodies), (
        "the Ironclad concession is discussed only obliquely in chat"
    )
    assert not any("residual" in body.lower() for body in chat_bodies)

    five = re.compile(r"\bfive\b|\(5\)|5-year", re.IGNORECASE)
    nda_email_bodies = [
        event.payload.body
        for event in full_log
        if isinstance(event.payload, EmailMessagePayload)
        and "NDA" in event.payload.subject
    ]
    assert not any(five.search(body) for body in nda_email_bodies), (
        "the accepted term length lives only in the version diff"
    )
    assert not any(five.search(body) for body in chat_bodies)


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

    decoys = [
        event
        for event in full_log
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and (
            "diligence" in event.payload.note.lower()
            or "data room" in event.payload.note.lower()
        )
        and _event_date(event) <= "2026-04-03"
    ]
    assert len(decoys) >= 3, "near-miss entries before the cutoff"

    cutoff_chats = [
        event
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.body == S2_CUTOFF_CHAT
    ]
    assert len(cutoff_chats) == 1 and _event_date(cutoff_chats[0]) == "2026-05-12"

    notes = [
        event
        for event in full_log
        if isinstance(event.payload, TicketCommentedPayload)
        and event.payload.ticket_id == S2_TICKET
        and "s2.note.resolution" in event.payload.body
    ]
    assert len(notes) == 1 and _event_date(notes[0]) == "2026-05-15"


def test_s2_support_audit_shapes_the_orphan_set(full_log: list) -> None:
    dm_ids = {
        event.payload.conversation_id
        for event in full_log
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
    }

    def referenced(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in S2_SUPPORT_MARKERS)

    coverage: dict[str, set[str]] = {}
    for event in full_log:
        payload = event.payload
        if isinstance(payload, EmailMessagePayload):
            text = f"{payload.subject} {payload.body}"
            if referenced(text):
                kind = "email-name" if "meridian" in text.lower() else "email-oblique"
                coverage.setdefault(_event_date(event), set()).add(kind)
        elif isinstance(payload, ChatMessagePayload) and referenced(payload.body):
            kind = "chat-dm" if payload.conversation_id in dm_ids else "chat-public"
            coverage.setdefault(_event_date(event), set()).add(kind)

    window = [
        event
        for event in full_log
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and "2026-04-03" < _event_date(event) <= "2026-04-30"
    ]
    assert len(window) >= 30, "the disputed window carries real volume"
    orphans = [event for event in window if _event_date(event) not in coverage]
    orphan_days = sorted({_event_date(event) for event in orphans})
    # The unsupported set is a graded deliverable: it must be a real
    # minority of the window, spread over several days, and never empty.
    assert orphans, "the support audit needs an answer"
    assert len(orphans) < len(window) / 3, orphan_days
    assert 3 <= len(orphan_days) <= 8, orphan_days

    window_days = {_event_date(event) for event in window}
    assert any(coverage.get(day) == {"chat-dm"} for day in window_days), (
        "at least one window day is supported only through a DM"
    )
    assert any(coverage.get(day) == {"email-oblique"} for day in window_days), (
        "at least one window day is supported only by a client-nameless email"
    )

    marcus_peter = next(
        event.payload.conversation_id
        for event in full_log
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
        and set(event.payload.members) == {"per-marcus-liang", "per-peter-novak"}
    )
    april_dm = [
        event
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id == marcus_peter
        and "2026-04-01" <= _event_date(event) <= "2026-04-30"
    ]
    assert len(april_dm) > 100, "the sprint pushes the DM window past one read"


def test_s3_indemnity_drops_silently_in_v4(full_log: list) -> None:
    lumen = _versions_by_title(full_log)[LUMEN_AGREEMENT_TITLE]
    assert set(lumen) == {1, 2, 3, 4, 5, 6, 7}
    for version in (1, 2, 3):
        assert INDEMNITY_PARAGRAPH in lumen[version]
    for version in (4, 5, 6, 7):
        assert INDEMNITY_PARAGRAPH not in lumen[version]

    summaries = {
        event.payload.revision: event.payload.change_summary
        for event in full_log
        if isinstance(event.payload, DocumentRevisedPayload)
        and event.payload.content.startswith("# Software License and Support")
    }
    assert set(summaries) == {2, 3, 4, 5, 6, 7}
    assert all("indemn" not in summary.lower() for summary in summaries.values()), (
        "the drop hides behind innocuous summaries"
    )
    assert "conform" in summaries[4].lower()
    assert not any(
        "conform" in summary.lower()
        for revision, summary in summaries.items()
        if revision != 4
    ), "the graded comment marker is unique to the dropping version"

    sow = _versions_by_title(full_log)[LUMEN_SOW_TITLE]
    assert set(sow) == {1, 2, 3, 4}
    assert all("Indemnification" not in content for content in sow.values())

    quotes = [
        event
        for event in full_log
        if isinstance(event.payload, EmailMessagePayload)
        and INDEMNITY_PARAGRAPH in event.payload.body
    ]
    assert len(quotes) == 1 and _event_date(quotes[0]) == "2026-06-09", (
        "the old clause text is quoted in email after the drop"
    )


FABRIC_TITLES = (
    "Engagement Letter (Standard Form)",
    "Matter Intake Checklist",
    "Billing & Time Entry Guidelines",
    "Litigation Hold Notice (Template)",
    "Discovery Response Playbook",
)


def test_fabric_grows_the_version_corpus_without_dropping(full_log: list) -> None:
    docs = _versions_by_title(full_log)
    multi = {title: v for title, v in docs.items() if len(v) >= 2}
    assert len(multi) >= 15, "exhaustive diffing must cost real work"
    assert sum(1 for v in multi.values() if len(v) >= 3) >= 5

    for title in FABRIC_TITLES:
        versions = docs[title]
        assert len(versions) >= 2, title
        ordered = [versions[number] for number in sorted(versions)]
        for previous, current in zip(ordered, ordered[1:], strict=False):
            for block in previous.split("\n\n"):
                assert block.strip() in current, (
                    f"{title}: fabric revisions only add; nothing disappears"
                )

    summaries = [
        event.payload.change_summary
        for event in full_log
        if isinstance(event.payload, DocumentRevisedPayload)
    ]
    assert all("indemn" not in summary.lower() for summary in summaries)


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
        and any(change.field == "status" for change in event.payload.changes)
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


def test_s5_operative_date_lives_only_in_the_dm_correction(full_log: list) -> None:
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
    assert "2026-06-25" not in scheduled_days

    dm_ids = {
        event.payload.conversation_id
        for event in full_log
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
    }
    assert dm_ids, "the correction DM conversation exists"

    corrections = [
        event
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.body == S5_DM_CORRECTION
    ]
    assert len(corrections) == 1
    assert _event_date(corrections[0]) == "2026-06-11"
    assert corrections[0].payload.conversation_id in dm_ids

    assert len(dm_ids) >= 8, "the DM fabric keeps enumeration from being free"
    thread = [
        event
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id == corrections[0].payload.conversation_id
    ]
    position = next(
        index
        for index, event in enumerate(thread)
        if event.payload.body == S5_DM_CORRECTION
    )
    assert len(thread) >= 60, "the correction DM is a long-running thread"
    assert position >= 5 and position <= len(thread) - 6, (
        "the correction sits mid-stream, not at either end of the DM"
    )
    for token in ("Arroyo", "Fruitvale", "hearing", "June"):
        assert token not in S5_DM_CORRECTION, "the DM text stays unsearchable"

    public_texts = [
        event.payload.body
        for event in full_log
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id not in dm_ids
    ] + [
        event.payload.body
        for event in full_log
        if isinstance(event.payload, EmailMessagePayload)
    ]
    assert not any("June 25" in text or "the 25th" in text for text in public_texts), (
        "the operative date leaks nowhere public"
    )

    recaps = [
        event
        for event in full_log
        if isinstance(event.payload, EmailMessagePayload)
        and event.payload.subject == S5_RECAP_SUBJECT
    ]
    assert len(recaps) == 1
    assert _event_date(recaps[0]) == "2026-06-16"
    assert "June 18" in recaps[0].payload.body
    assert int(recaps[0].time) > int(corrections[0].time), (
        "the stale recap postdates the DM correction"
    )

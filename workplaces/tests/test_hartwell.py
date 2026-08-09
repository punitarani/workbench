"""Hartwell & Marsh structural acceptance: genesis coherence, cast shape,
and the pilot history build."""

import importlib.util
from pathlib import Path
from types import ModuleType

from workbench.core.events.chat import ChatConversationCreatedPayload
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.tools import check_coherence
from workbench.workplaces.hartwell import (
    EPOCH_ISO,
    WINDOW,
    WORKPLACE_ID,
    build_genesis,
    procedural_cast,
)
from workbench.workplaces.hartwell.people import (
    CLIENT_ORGS,
    EMPLOYEES,
    EXTERNALS,
    ORGS,
    TIMEKEEPER_IDS,
)


def _load_build_history() -> ModuleType:
    path = Path(__file__).parents[2] / "datasets" / "hartwell" / "build_history.py"
    spec = importlib.util.spec_from_file_location("hartwell_build_history", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_genesis_validates_with_zero_findings() -> None:
    genesis = build_genesis(Seed(root=42))
    report = validate_events(list(genesis.events))
    assert report.findings == ()
    opening = genesis.events[0].payload
    assert opening.kind == "sim.run.started"
    assert opening.workplace_id == WORKPLACE_ID == "hartwell"
    assert opening.epoch == EPOCH_ISO == "2026-03-02T00:00:00-08:00"
    assert opening.timezone == "America/Los_Angeles"


def test_genesis_is_deterministic() -> None:
    first = build_genesis(Seed(root=42))
    second = build_genesis(Seed(root=42))
    assert [event.model_dump_json() for event in first.events] == [
        event.model_dump_json() for event in second.events
    ]


def test_cast_counts_and_roles() -> None:
    assert len(EMPLOYEES) == 12
    assert len(CLIENT_ORGS) == 12
    assert len(EXTERNALS) == 14

    assert len({person.person_id for person in (*EMPLOYEES, *EXTERNALS)}) == 26
    assert len({person.name for person in (*EMPLOYEES, *EXTERNALS)}) == 26
    assert all(person.affiliation == "internal" for person in EMPLOYEES)
    assert all(person.affiliation == "external" for person in EXTERNALS)
    assert all(org.category == "client" for org in CLIENT_ORGS)

    titles = [person.title for person in EMPLOYEES]
    partners = [t for t in titles if t.endswith("Partner")]
    assert len(partners) == 2
    assert sum("Of Counsel" in t for t in titles) == 1
    assert sum("Associate" in t for t in titles) == 3
    assert sum("Paralegal" in t for t in titles) == 2


def test_externals_reference_real_organizations() -> None:
    org_ids = {org.org_id for org in ORGS}
    for person in EXTERNALS:
        assert person.organization in org_ids, person.person_id


def test_channels_have_topic_and_purpose() -> None:
    genesis = build_genesis(Seed(root=42))
    channels = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, ChatConversationCreatedPayload)
    ]
    assert {channel.name for channel in channels} == {
        "#general",
        "#matters",
        "#billing",
        "#it-help",
    }
    employee_ids = {person.person_id for person in EMPLOYEES}
    for channel in channels:
        assert channel.topic, channel.name
        assert channel.purpose, channel.name
        assert set(channel.members) <= employee_ids
    general = next(channel for channel in channels if channel.name == "#general")
    assert set(general.members) == employee_ids


def test_matters_reference_real_orgs_and_people() -> None:
    genesis = build_genesis(Seed(root=42))
    matters = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, TicketCreatedPayload)
    ]
    assert len(matters) == 10
    client_org_ids = {org.org_id for org in CLIENT_ORGS}
    person_ids = {person.person_id for person in (*EMPLOYEES, *EXTERNALS)}
    employee_ids = {person.person_id for person in EMPLOYEES}
    assignees = set()
    for matter in matters:
        assert matter.client_ref in client_org_ids, matter.ticket_id
        assert matter.actor in employee_ids
        assert matter.requester in person_ids
        assert matter.assignee in employee_ids
        assert matter.status == "open"
        assignees.add(matter.assignee)
    assert len(assignees) >= 4, "matters spread across the attorneys"


def test_seed_documents_carry_real_content() -> None:
    genesis = build_genesis(Seed(root=42))
    documents = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, DocumentCreatedPayload)
    ]
    assert len(documents) == 8
    employee_ids = {person.person_id for person in EMPLOYEES}
    assert len({document.path for document in documents}) == 8
    for document in documents:
        assert document.author in employee_ids
        assert len(document.content) > 300, document.path


def test_final_minter_covers_every_minted_prefix() -> None:
    genesis = build_genesis(Seed(root=42))
    counters = genesis.minter.counters
    assert counters["org"] == len(ORGS)
    assert counters["cnv"] == 4
    assert counters["doc"] == 8
    assert counters["tkt"] == 10


def test_procedural_cast_resolves_against_genesis() -> None:
    genesis = build_genesis(Seed(root=42))
    cast = procedural_cast(genesis)
    assert len(cast.internal) == 12
    assert len(cast.externals) == 14
    assert {member.person_id for member in cast.timekeepers} == set(TIMEKEEPER_IDS)
    assert cast.standup_channel.startswith("cnv-")
    assert len(cast.matters) == 10


def test_pilot_build_validates_projects_and_coheres(tmp_path: Path) -> None:
    module = _load_build_history()
    assert module.main(["--out", str(tmp_path)]) == 0

    events = read_events(tmp_path / "world.jsonl")
    report = validate_events(events)
    assert report.findings == ()
    started = [event for event in events if event.tag == "sim.day.started"]
    assert [event.payload.day for event in started] == [
        WINDOW.iso_date(index) for index in WINDOW.workdays()[:5]
    ]

    state = tmp_path / "pilot-workspace" / "state"
    assert {path.name for path in state.glob("*.db")} == {
        "gmail.db",
        "slack.db",
        "imanage.db",
        "clio.db",
    }
    assert check_coherence(state) == ()
    environment = (tmp_path / "pilot-workspace" / "environment.toml").read_text()
    assert "seat" not in environment, "the pilot workspace is seatless"


def test_pilot_build_determinism_check(tmp_path: Path) -> None:
    module = _load_build_history()
    assert module.main(["--out", str(tmp_path), "--check"]) == 0

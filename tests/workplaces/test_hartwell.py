"""Hartwell & Marsh structural acceptance: genesis coherence, cast shape,
and the pilot history build."""

import importlib.util
from collections import Counter
from pathlib import Path
from types import ModuleType

from core.events.chat import ChatConversationCreatedPayload
from core.events.documents import DocumentCreatedPayload
from core.events.tickets import TicketCreatedPayload
from core.seed import Seed
from core.worldlog import read_events, validate_events
from tools import check_coherence
from workplaces.hartwell import (
    EPOCH_ISO,
    FEDERAL_HOLIDAYS_2026,
    WINDOW,
    WORKPLACE_ID,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workplaces.hartwell.people import (
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
    # 15 since the September continuation added Goldleaf's opposing counsel.
    assert len(EXTERNALS) == 15

    assert len({person.person_id for person in (*EMPLOYEES, *EXTERNALS)}) == 27
    assert len({person.name for person in (*EMPLOYEES, *EXTERNALS)}) == 27
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
    conversations = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, ChatConversationCreatedPayload)
    ]
    channels = [c for c in conversations if c.conversation_type == "channel"]
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

    dms = [c for c in conversations if c.conversation_type == "dm"]
    assert len(dms) >= 8, "the DM fabric needs standing pairs"
    pairs = {frozenset(dm.members) for dm in dms}
    assert len(pairs) == len(dms), "each pair gets exactly one DM"
    for dm in dms:
        assert dm.name is None
        assert len(dm.members) == 2
        assert set(dm.members) <= employee_ids
    assert frozenset(("per-grace-adeyemi", "per-samuel-marsh")) in pairs


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
    assert counters["cnv"] == 4 + 12
    assert counters["doc"] == 8
    assert counters["tkt"] == 10


def test_procedural_cast_resolves_against_genesis() -> None:
    genesis = build_genesis(Seed(root=42))
    cast = procedural_cast(genesis)
    assert len(cast.internal) == 12
    assert len(cast.externals) == 14
    assert {keeper.member.person_id for keeper in cast.timekeepers} == set(
        TIMEKEEPER_IDS
    )
    assert all(keeper.rate_cents > 0 for keeper in cast.timekeepers)
    assert all(4.0 <= keeper.daily_hours <= 8.0 for keeper in cast.timekeepers)
    weights = sorted(matter.weight for matter in cast.matters)
    assert weights[-1] >= 4 * weights[0], "matter complexity must spread"
    assert all(matter.assignee in matter.team() for matter in cast.matters)
    assert cast.standup_channel.startswith("cnv-")
    assert len(cast.matters) == 10
    assert len(cast.dms) == 12
    grace_samuel = next(
        dm
        for dm in cast.dms
        if {member.person_id for member in dm.members}
        == {"per-grace-adeyemi", "per-samuel-marsh"}
    )
    assert grace_samuel.traffic == max(dm.traffic for dm in cast.dms), (
        "the correction thread runs hottest"
    )


def test_day_profile_covers_the_whole_calendar() -> None:
    seed = Seed(root=42)
    profiles = [day_profile(seed, index) for index in range(WINDOW.day_count)]
    kinds = Counter(profile.kind for profile in profiles)
    # 87 weekdays, of which Memorial Day and Juneteenth are observed.
    # March 2 - September 30: the continuation doubled the horizon.
    assert kinds == {"workday": 149, "weekend": 60, "holiday": 4}
    assert all(profile.intensity > 0 for profile in profiles), (
        "no day is completely silent"
    )
    weekends = [p.intensity for p in profiles if p.kind == "weekend"]
    assert max(weekends) < 0.2 and len(set(weekends)) == len(weekends), (
        "weekends are thin and none is a copy of another"
    )
    in_window = {
        day
        for day, _, _ in FEDERAL_HOLIDAYS_2026
        if WINDOW.start_date <= day <= WINDOW.end_date
    }
    # Independence Day observed and Labor Day fall inside the continuation.
    assert in_window == {"2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07"}


def test_day_profile_is_deterministic() -> None:
    seed = Seed(root=42)
    assert [day_profile(seed, index) for index in range(WINDOW.day_count)] == [
        day_profile(seed, index) for index in range(WINDOW.day_count)
    ]


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

    bundle = tmp_path / "pilot-bundle"
    state = bundle / "state"
    assert {path.name for path in state.glob("*.db")} == {
        "gmail.db",
        "slack.db",
        "imanage.db",
        "clio.db",
        "calendar.db",
    }
    assert check_coherence(state) == ()
    environment = (bundle / "environment.toml").read_text()
    assert "seat" not in environment, "the pilot bundle is seatless"
    assert list((bundle / "workspace").rglob("*.db")) == [], (
        "the agent's workspace never holds the tool databases"
    )


def test_pilot_build_determinism_check(tmp_path: Path) -> None:
    module = _load_build_history()
    assert module.main(["--out", str(tmp_path), "--check"]) == 0

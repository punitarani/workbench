"""What the reachability crawl models is *honest navigation*, and it must
not be shallower than the surface it gates.

The crawl starts with no ids, lists and searches, then opens what those
results named. That was one round of opening, and iManage needs two: a
workspace names its documents, and only a document names its versions.
Nothing in step one returns a bare document reference at all -- the
recents feed returns version-qualified ids -- so the version lists of
every document not recently touched were never fetched.

Measured on a six-month world: 105 `LEGAL!` ids discovered, not one of
them a bare document id, and `LEGAL!24.6` reported as a value no tool
ever serves. `get_document_versions("24")` returns it without complaint.
The task whose oracle named it was blocked, and its answer key was right.

A false positive here is not a small thing. The gate's whole job is to
say "no agent could produce this", and when it says that wrongly, the
correct response looks like rewriting a good rule.
"""

import asyncio

import pytest

from core.events import Event
from core.events.control import SimRunStartedPayload
from core.events.documents import DocumentCreatedPayload, DocumentRevisedPayload
from core.events.people import PersonRecordPayload
pytest.importorskip("mcp.server")

# Enough documents that the one under test does not have a number small
# enough to turn up by accident. The first draft of this fixture had a
# single document, number 1 -- and "1" appears in step one anyway as a
# page number and a document count, so `get_document_versions("1")`
# resolved it and every version was "reachable" at any depth. The test
# passed against the bug it was written to catch.
DOCUMENTS = 12
PROBE_NUMBER = 7
REVISIONS = 6


def _events() -> list[Event]:
    payloads = [
        # Without this the database carries no epoch and every profile
        # call raises, which the crawl swallows as "unresolvable" -- the
        # fixture would then prove the crawl reaches nothing rather than
        # anything about its depth.
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-test-1",
            seed_root=42,
            workplace_id="test",
            config_hash="0" * 64,
            schema_version=1,
            epoch="2026-01-05T00:00:00+00:00",
            timezone="UTC",
        ),
        PersonRecordPayload(
            kind="person.record",
            person_id="per-ana",
            name="Ana Reyes",
            email_address="ana@example.test",
            title="Associate",
            department="Litigation",
            manager=None,
            affiliation="internal",
            timezone="UTC",
        ),
    ]
    for number in range(1, DOCUMENTS + 1):
        payloads.append(
            DocumentCreatedPayload(
                kind="document.created",
                document_id=f"doc-{number:06d}",
                author="per-ana",
                title=f"Opposition to Motion to Compel {number}",
                path=f"engagements/hollstead/opposition-{number}.docx",
                location="repository",
                content_format="formatted",
                content="{}",
            )
        )
    for revision in range(2, REVISIONS + 1):
        payloads.append(
            DocumentRevisedPayload(
                kind="document.revised",
                document_id=f"doc-{PROBE_NUMBER:06d}",
                author="per-ana",
                revision=revision,
                content="{}",
                change_summary=f"pass {revision}",
            )
        )
    return [
        Event(
            seq=index,
            event_id=f"evt-{index:06d}",
            time=index * 3600,
            tag=payload.kind,
            source="gm",
            payload=payload,
        )
        for index, payload in enumerate(payloads, start=1)
    ]


@pytest.fixture
def state(tmp_path):
    from tools.imanage import SYSTEM
    from tools.framework import project_system

    state_dir = tmp_path / "state"
    project_system(SYSTEM, _events(), state_dir / "imanage.db")
    return state_dir


def test_a_deep_version_is_reachable(state) -> None:
    """The version that only a document's own history names.

    Reaching it takes three moves: search the workspaces, list the
    workspace's children, then ask a document for its versions. Two moves
    stop at the head profile.
    """

    from analysis.reachability import _served

    reached = asyncio.run(_served(state))
    deep = f"LEGAL!{PROBE_NUMBER}.2"
    assert deep in reached, (
        f"{deep} is what get_document_versions returns; a crawl that cannot "
        "reach it will call a correct oracle unservable"
    )


def test_every_version_is_reachable_not_just_the_head(state) -> None:
    """The head arrives from the document profile at any depth, so an
    assertion naming only the newest version passes without the fix."""

    from analysis.reachability import _served

    reached = asyncio.run(_served(state))
    missing = [
        f"LEGAL!{PROBE_NUMBER}.{version}"
        for version in range(1, REVISIONS + 1)
        if f"LEGAL!{PROBE_NUMBER}.{version}" not in reached
    ]
    assert not missing, missing


def test_the_head_was_always_reachable(state) -> None:
    """Pins the half that already worked, so a change that deepens the
    crawl cannot quietly lose the shallow results."""

    from analysis.reachability import _served

    reached = asyncio.run(_served(state))
    assert f"LEGAL!{PROBE_NUMBER}.{REVISIONS}" in reached


def test_the_crawl_terminates(state) -> None:
    """Following what the follow found is a fixed-point walk, and only the
    depth bound stops it. A crawl that does not stop is not a gate, it is
    a hang somebody kills.

    Asserted by running it rather than by reading the constant: a test
    that checks `_MAX_DEPTH >= 2` passes whatever the crawl does.
    """

    from analysis.reachability import _served

    reached = asyncio.run(_served(state))
    assert reached


# --- the walk itself ---------------------------------------------------
#
# The fixtures above cannot show the defect, and finding out why was the
# useful part. At twelve documents `get_recent_documents` names every one
# of them in step one, so a single follow round reaches every version and
# the crawl looks correct. The defect needs a world big enough that most
# documents are not in the recents -- and a test that has to build one is
# a test nobody runs.
#
# So the walk is exercised directly, against a server whose only path to
# the third value runs through the second.


class _Tool:
    def __init__(self, name: str, required: list[str]) -> None:
        self.name = name
        self.input_schema = {"required": required}


class _Chain:
    """workspace -> document -> version, and no shortcuts.

    Deliberately not a substring or prefix relationship: a walk that
    happened to guess `deep-version` from `document` would pass.
    """

    LINKS = {"workspace": "document", "document": "deep-version"}

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def call_tool(self, name: str, arguments: dict):
        (value,) = arguments.values()
        self.asked.append(value)
        return {"data": [{"id": self.LINKS[value]}]} if value in self.LINKS else {}


async def _walk(server, discovered):
    from analysis.reachability import _follow

    return await _follow(server, [_Tool("open", ["id"])], discovered)


def test_the_walk_reaches_the_third_link(monkeypatch) -> None:
    from analysis import reachability

    async def collect(server, name, arguments, into):
        got = await server.call_tool(name, arguments)
        for row in got.get("data", []):
            into.update(str(v) for v in row.values())

    monkeypatch.setattr(reachability, "_collect", collect)
    server = _Chain()
    reached = asyncio.run(_walk(server, {"workspace"}))
    assert "document" in reached
    assert "deep-version" in reached, (
        "the version is only named by the document, which is only named by "
        "the workspace -- one follow round stops at the document"
    )


def test_the_walk_does_not_re_ask_what_it_already_asked(monkeypatch) -> None:
    """Rounds must not re-follow earlier candidates, or the cost is the
    square of everything seen rather than rounds x cap."""

    from analysis import reachability

    async def collect(server, name, arguments, into):
        got = await server.call_tool(name, arguments)
        for row in got.get("data", []):
            into.update(str(v) for v in row.values())

    monkeypatch.setattr(reachability, "_collect", collect)
    server = _Chain()
    asyncio.run(_walk(server, {"workspace"}))
    assert len(server.asked) == len(set(server.asked)), server.asked

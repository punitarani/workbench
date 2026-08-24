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
    from tools.framework import project_system
    from tools.imanage import SYSTEM

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


# One container holding more than a page. iManage serves a hundred children
# a page and names the next one in `next_page`; it sends no `hasMore`, which
# is the field the crawl's page branch looked for. Absent, it read as "no
# more pages" and every container stopped at its first hundred.
#
# Measured on the six-month Merrick record: 221 of 658 documents opened, and
# the version ids of the other 437 reported as values no tool ever serves --
# which blocked a task whose key was correct. One page is not a surface.
PAGED_DOCUMENTS = 150
PAGED_PROBE = 140


def _paged_events() -> list[Event]:
    payloads = [
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-test-2",
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
    for number in range(1, PAGED_DOCUMENTS + 1):
        payloads.append(
            DocumentCreatedPayload(
                kind="document.created",
                document_id=f"doc-{number:06d}",
                author="per-ana",
                title=f"Deposition Summary {number}",
                path=f"engagements/hollstead/summary-{number}.docx",
                location="repository",
                content_format="formatted",
                content="{}",
            )
        )
    # Revised, so its version list carries an id the head profile never
    # names -- the probe has to be a value only the deep call returns.
    payloads.append(
        DocumentRevisedPayload(
            kind="document.revised",
            document_id=f"doc-{PAGED_PROBE:06d}",
            author="per-ana",
            revision=2,
            content="{}",
            change_summary="second pass",
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
def paged_state(tmp_path):
    from tools.framework import project_system
    from tools.imanage import SYSTEM

    state_dir = tmp_path / "paged"
    project_system(SYSTEM, _paged_events(), state_dir / "imanage.db")
    return state_dir


def test_a_container_is_paged_to_its_end(paged_state) -> None:
    """A document on the second page of its workspace is still reachable.

    `PAGED_PROBE` is past the first hundred deliberately: a probe inside
    page one passes whether or not the crawl pages at all, which is how
    this went unnoticed. Its *second version* is the assertion, because the
    head turns up in the recents feed on its own.
    """

    from analysis.reachability import _served

    reached = asyncio.run(_served(paged_state))
    assert f"LEGAL!{PAGED_PROBE}.1" in reached, (
        "the document itself is past page one of its container; a crawl "
        "that stops at the first page never opens it"
    )
    assert f"LEGAL!{PAGED_PROBE}.2" in reached, (
        "and its version list is what names this one"
    )


# --- the page branch itself, with no world behind it -------------------
#
# The fixture above cannot isolate this: a 150-document world is small
# enough that the recents feed names every document on its own, so the
# probe stays reachable with pagination broken. The defect only bites once
# the OTHER routes cap out -- iManage stops a search at 500 results -- and
# building a 600-document fixture to prove one branch is the wrong trade.
# So the branch is exercised directly, against a server that paginates the
# way iManage does and says nothing about `hasMore`.


class _PagingChunk:
    def __init__(self, text: str) -> None:
        self.text = text


class _PagingResult:
    def __init__(self, text: str) -> None:
        self.is_error = False
        self.content = [_PagingChunk(text)]


class _PagingTool:
    name = "get_container_children"
    input_schema = {"properties": {"container_id": {}, "page": {}}}


class _PagingServer:
    """Three pages, `next_page`, and no `hasMore` -- iManage's shape."""

    PAGES = 3
    PER_PAGE = 2

    def __init__(self) -> None:
        self.pages_served: list[int] = []

    async def list_tools(self):
        return [_PagingTool()]

    async def call_tool(self, name, arguments):
        import json as _json

        page = arguments.get("page") or 1
        self.pages_served.append(page)
        start = (page - 1) * self.PER_PAGE
        data = [
            {"id": f"LEGAL!{start + offset + 1}.1"} for offset in range(self.PER_PAGE)
        ]
        payload = {"data": data, "next_page": page + 1 if page < self.PAGES else None}
        return _PagingResult(_json.dumps(payload))


def test_a_next_page_token_is_followed_without_a_hasmore_flag() -> None:
    """`next_page` names the next page; nothing else has to agree.

    The page branch used to require `hasMore`, and returned as soon as it
    was absent -- so a surface that paginates by naming its successor was
    read as a single page. Every id past the first hundred children of a
    container went unseen, and the gate reported correct oracle values as
    unservable.
    """

    from analysis.reachability import _collect

    server = _PagingServer()
    found: set[str] = set()
    asyncio.run(
        _collect(server, "get_container_children", {"container_id": "W1"}, found)
    )

    assert server.pages_served == [1, 2, 3], (
        f"every page has to be asked for, got {server.pages_served}"
    )
    assert "LEGAL!5.1" in found and "LEGAL!6.1" in found, (
        "the last page's ids are as reachable as the first page's"
    )

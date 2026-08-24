"""Two documents cannot occupy one path, and the record must not claim they do.

A file room is a filesystem: the second write to a path overwrites the
first. The referee allowed it, so the record said fifteen documents while
the folder held thirteen, and the earlier work was invisible to anything
reading the surface — including a task grading it.

Measured on a real world: three separate documents named
`closing-checklist.xlsx` in one matter folder. Two in fifteen is 13%, and
this window will produce roughly four hundred and fifty documents.

Rejecting rather than silently versioning is deliberate. The persona
wanted a document that already exists, and a rejection it can read names
the one to work forward — which is what the deliverable turn is for, and
a third of those turns are meant to be revisions rather than first
drafts.

**This drives the real referee.** The first version of this file
reimplemented the check as a local helper and asserted against that,
which is the same defect an audit had just caught elsewhere in this
tree — a test transcribing the code it is supposed to be testing passes
happily while the real path diverges. A test that contains its own copy
of the logic tests the copy.
"""

import pytest

from core.events import Event
from core.events.control import SimDeliverablePayload
from core.intents import DocumentCreateSpec, DocumentEditIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary


def _gm() -> GroundedGm:
    return GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )


def _event() -> Event:
    return Event(
        seq=1,
        event_id="evt-000001",
        time=0,
        tag="sim.deliverable",
        source="gm",
        payload=SimDeliverablePayload(
            kind="sim.deliverable", entity="ana", day="2026-01-05"
        ),
    )


def _create(path: str) -> DocumentEditIntent:
    return DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Closing checklist",
            path=path,
            content="a note",
            content_format="markdown",
        ),
    )


def _commit(gm: GroundedGm, draft) -> None:
    """Put a grounded draft into world state, as the engine does.

    `WorldState.apply` takes an `Event`, not a payload — wrapping it here
    keeps the test on the same path the runtime uses instead of poking
    the state dictionaries directly.
    """

    gm.world.apply(
        Event(
            seq=2,
            event_id="evt-000002",
            time=0,
            tag=draft.tag,
            source="gm",
            payload=draft.payload,
        )
    )


def _ground(gm: GroundedGm, path: str):
    """Ground a create through the referee itself.

    `_ground_document` is the real code the engine reaches; the repo's
    other grounding tests drive the `_ground_*` methods the same way.
    What matters is that nothing here reimplements the rule.
    """

    return gm._ground_document("ana", "per-ana", _create(path), _event(), 0)


def test_a_free_path_is_accepted() -> None:
    gm = _gm()
    drafts = _ground(gm, "engagements/a/memo.docx")
    assert [d.tag for d in drafts] == ["document.created"]


def test_a_taken_path_is_rejected_and_names_the_document() -> None:
    """The note has to say *which* document, or the persona cannot act on
    it and simply tries a different filename."""

    gm = _gm()
    path = "engagements/northmoor/closing-checklist.xlsx"
    first = _ground(gm, path)
    document_id = first[0].payload.document_id
    _commit(gm, first[0])

    with pytest.raises(IntentRejection) as caught:
        _ground(gm, path)
    assert document_id in caught.value.reason
    assert "revise" in caught.value.reason


def test_the_real_collision_that_motivated_this() -> None:
    """Three documents, one path, in a recorded world."""

    gm = _gm()
    path = "engagements/northmoor/sandhurst-platform-acquisition/closing-checklist.xlsx"
    first = _ground(gm, path)
    _commit(gm, first[0])
    for _ in range(2):
        with pytest.raises(IntentRejection):
            _ground(gm, path)
    assert len(gm.world.document_paths_by_id) == 1


def test_paths_differing_only_in_folder_are_distinct() -> None:
    """Two matters may each hold a closing checklist; that is not a
    collision, and rejecting it would be worse than the defect."""

    gm = _gm()
    first = _ground(gm, "a/closing-checklist.xlsx")
    _commit(gm, first[0])
    second = _ground(gm, "b/closing-checklist.xlsx")
    assert [d.tag for d in second] == ["document.created"]


def test_the_record_never_gains_the_second_document() -> None:
    """A rejection that still minted an id would leave the record claiming
    two documents where the folder holds one — the very state this
    prevents, arrived at from the other side."""

    gm = _gm()
    path = "a/one.docx"
    _commit(gm, _ground(gm, path)[0])
    before = dict(gm.world.document_paths_by_id)
    with pytest.raises(IntentRejection):
        _ground(gm, path)
    assert gm.world.document_paths_by_id == before


def test_two_matters_may_each_have_their_own_tracker() -> None:
    """Documents differing in an intermediate directory are two documents.

    This test used to assert the opposite, and its docstring described the
    defect as the design: `filed_name` kept only the top-level segment, so
    every matter in the firm shared one flat namespace and the second
    `diligence-status-tracker.xlsx` was refused.

    What that cost, measured on a six-month world: 304 of 308 documents
    were not at the path iManage served for them, so an agent that read a
    path and opened it failed 98.7% of the time. And because the obvious
    names collided, personas invented new ones until **24 of those 308
    documents were the same WIP report under twenty-four different names**.
    """

    gm = _gm()
    first = "engagements/northmoor/sandhurst-add-on/diligence-status-tracker.xlsx"
    second = "engagements/northmoor/sandhurst-platform/diligence-status-tracker.xlsx"
    _commit(gm, _ground(gm, first)[0])
    _commit(gm, _ground(gm, second)[0])  # must not raise


def test_the_collision_the_declared_path_cannot_see() -> None:
    """The extension is decided by the format, not by the name.

    So two distinct declared paths still become one file when they differ
    only in a suffix the format overrides — a workbook called `.docx` is
    filed as `.xlsx` like every other workbook. The declared paths are
    different strings and the file is the same file, which is why the
    guard keys on `filed_name` rather than on what the author wrote.
    """

    gm = _gm()
    first = "engagements/northmoor/sandhurst/closing-checklist.xlsx"
    second = "engagements/northmoor/sandhurst/closing-checklist.docx"
    assert first != second
    _commit(gm, _ground(gm, first)[0])
    with pytest.raises(IntentRejection) as caught:
        _ground(gm, second)
    assert "engagements/northmoor/sandhurst/closing-checklist" in caught.value.reason


def test_a_create_is_reserved_at_resolve_time() -> None:
    """Every create in a cohort resolves before any draft is applied, so
    a guard reading applied state sees an empty room. Three documents
    reached one file with no rejection at all — the revision branch below
    already bumps its head for exactly this reason."""

    gm = _gm()
    path = "engagements/a/tracker.xlsx"
    _ground(gm, path)  # resolved, deliberately NOT committed
    with pytest.raises(IntentRejection):
        _ground(gm, path)


def test_a_declared_suffix_that_lies_still_collides() -> None:
    """The name follows the bytes: a workbook named `.docx` is filed as
    `.xlsx`. Two such documents collide even though their declared paths
    differ in the suffix."""

    gm = _gm()
    _commit(gm, _ground(gm, "engagements/a/report.md")[0])
    with pytest.raises(IntentRejection):
        _ground(gm, "engagements/a/report.md")


def test_a_document_with_no_content_is_refused() -> None:
    """Nine documents in a six-month world were created empty and
    materialized as zero-byte files.

    A count by suffix cannot see this: they are nine real .docx entries to
    every check that asks how many documents exist. Only reading the bytes
    finds them, and by then the work is lost.
    """

    gm = _gm()
    empty = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Counterclaim strategy position",
            path="engagements/verity-grain/counterclaim-strategy.docx",
            content="",
            content_format="markdown",
        ),
    )
    with pytest.raises(IntentRejection) as caught:
        gm._ground_document("ana", "per-ana", empty, _event(), 0)
    assert "no content" in caught.value.reason


def test_whitespace_is_not_content() -> None:
    gm = _gm()
    blank = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Blank",
            path="engagements/a/blank.docx",
            content="   \n\t  \n",
            content_format="markdown",
        ),
    )
    with pytest.raises(IntentRejection):
        gm._ground_document("ana", "per-ana", blank, _event(), 0)


def test_a_refused_empty_document_reserves_no_path() -> None:
    """The collision guard reserves a filed name at resolve time. If the
    emptiness check ran after that, the rejection would burn the path and
    the persona's retry -- with real content this time -- would collide
    with a document that was never created."""

    gm = _gm()
    path = "engagements/a/strategy.docx"
    empty = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Strategy", path=path, content="", content_format="markdown"
        ),
    )
    with pytest.raises(IntentRejection):
        gm._ground_document("ana", "per-ana", empty, _event(), 0)
    drafts = _ground(gm, path)
    assert [d.tag for d in drafts] == ["document.created"]


def test_a_workbook_with_no_rows_is_refused() -> None:
    """`formatted` and `slides` already refuse their empty equivalents;
    a spreadsheet of column headings and no rows parses cleanly and is
    empty in the only sense that matters."""

    gm = _gm()
    headers_only = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Diligence tracker",
            path="engagements/a/tracker.xlsx",
            content='{"sheets": [{"name": "Items", "columns": ["Item"], "rows": []}]}',
            content_format="spreadsheet",
        ),
    )
    with pytest.raises(IntentRejection) as caught:
        gm._ground_document("ana", "per-ana", headers_only, _event(), 0)
    assert "no rows" in caught.value.reason


def test_a_malformed_document_does_not_burn_its_filename() -> None:
    """Every content rejection used to happen after the filed name was
    claimed, so a persona whose JSON was malformed lost that filename for
    the rest of the run — and its retry, with correct content, collided
    with a document that had never been created."""

    gm = _gm()
    path = "engagements/a/tracker.xlsx"
    broken = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Diligence tracker",
            path=path,
            content="not json at all",
            content_format="spreadsheet",
        ),
    )
    with pytest.raises(IntentRejection):
        gm._ground_document("ana", "per-ana", broken, _event(), 0)

    fixed = DocumentEditIntent(
        document_ref=None,
        create=DocumentCreateSpec(
            title="Diligence tracker",
            path=path,
            content=(
                '{"sheets": [{"name": "Items", "columns": ["Item"], '
                '"rows": [["Open items"]]}]}'
            ),
            content_format="spreadsheet",
        ),
    )
    drafts = gm._ground_document("ana", "per-ana", fixed, _event(), 0)
    assert [d.tag for d in drafts] == ["document.created"]

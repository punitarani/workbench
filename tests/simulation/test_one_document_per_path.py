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

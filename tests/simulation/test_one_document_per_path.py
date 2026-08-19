"""Two documents cannot occupy one path, and the record must not claim they do.

A file room is a filesystem: the second write to a path overwrites the
first. The referee allowed it, so the record said fifteen documents while
the folder held thirteen, and the earlier work was invisible to anything
reading the surface — including a task grading it.

Measured on a real world: three separate documents named
`closing-checklist.xlsx` in one matter folder. Two in fifteen is 13%, and
this world will produce roughly four hundred and fifty documents.

Rejecting rather than silently versioning is deliberate. The persona
wanted a document that already exists, and a rejection it can read names
the one to work forward — which is what the deliverable turn is for, and
a third of those turns are meant to be revisions rather than first
drafts.
"""

import pytest

from simulation.gm.grounded import IntentRejection


class _World:
    def __init__(self, paths: dict[str, str]) -> None:
        self.document_paths_by_id = paths


def _reject_if_taken(world: _World, path: str) -> None:
    """The check as the referee performs it."""

    existing = {p: i for i, p in world.document_paths_by_id.items()}.get(path)
    if existing is not None:
        raise IntentRejection(
            f"{path} already exists as {existing}; revise that document "
            "instead of writing over it, or file this one under a name of "
            "its own"
        )


def test_a_free_path_is_allowed() -> None:
    world = _World({"doc-000001": "engagements/a/memo.docx"})
    _reject_if_taken(world, "engagements/a/other.docx")


def test_a_taken_path_is_rejected_and_names_the_document() -> None:
    """The note has to say *which* document, or the persona cannot act on
    it and simply tries a different filename."""

    world = _World({"doc-000008": "northmoor/closing-checklist.xlsx"})
    with pytest.raises(IntentRejection) as caught:
        _reject_if_taken(world, "northmoor/closing-checklist.xlsx")
    message = str(caught.value)
    assert "doc-000008" in message
    assert "revise" in message


def test_the_real_collision_that_motivated_this() -> None:
    """Three documents, one path, in a recorded world."""

    world = _World({})
    path = "engagements/northmoor/sandhurst-platform-acquisition/closing-checklist.xlsx"
    _reject_if_taken(world, path)
    world.document_paths_by_id["doc-000008"] = path
    for attempt in ("doc-000010", "doc-000011"):
        with pytest.raises(IntentRejection):
            _reject_if_taken(world, path)
        assert attempt not in world.document_paths_by_id


def test_paths_differing_only_in_folder_are_distinct() -> None:
    """Two matters may each hold a closing checklist; that is not a
    collision and rejecting it would be worse than the defect."""

    world = _World({"doc-1": "a/closing-checklist.xlsx"})
    _reject_if_taken(world, "b/closing-checklist.xlsx")

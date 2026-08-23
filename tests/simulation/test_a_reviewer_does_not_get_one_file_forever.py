"""Peer review picks a file by a number that never changes.

`grounded.py` hands a person a colleague's document to review on one of
three deliverable phases:

    elif phase == 1 and colleagues:
        candidate = colleagues[offset % len(colleagues)]

`offset` is the person's index in the sorted roster, fixed for the run.
`colleagues` is every document somebody else wrote, in creation order, and
passes 17 entries on the first day -- so `offset % len(colleagues)` **is**
`offset`, always, and each person is permanently assigned one file to
review, chosen by their alphabetical rank.

Measured on the v6 record -- 68 days, not the six months an earlier
version of this docstring claimed: 139 review versions, 18 reviewers, and
**17 distinct documents reviewed out of 451**. Twelve of the eighteen
reviewers reviewed exactly one document for the whole recording. The
median reviewer put 100% of their reviews on a single file.

The lock is measurable while a run is still going. `colleagues` only grows
by appending, so once the file room passes the roster size -- the first day
or two -- the modulo stops biting and the pick freezes. On the live v7
recording, 30 of 325 documents have a second reader and **no reviewer has
been handed a document they had not already reviewed in 26 days**.

The branch is not dead code and it is not unreached -- it fires 224 times.
It is the subtler thing: code that runs, does something, and can only ever
do one thing. The comment four lines above it diagnoses precisely this
about the surrounding *phase* -- "authorship never moves once a document
exists, so a phase counted from documents I wrote sticks on whichever
branch it first reaches" -- and then the selection inside the branch
indexes on a quantity that never moves at all.

It reaches the record, too: a person handed an unrelated file writes that
down. 16 revision comments say so outright, and 8 of the rate card's 19
versions are that sentence in different words.

Marked xfail(strict) rather than fixed here: `simulation/gm/grounded.py` is
one of the seven files whose byte digest keys resume, and a recording is
running. Strict is the point -- when the fix lands this test XPASSes, which
is a failure, and whoever lands it has to come here and delete the marker
rather than leave a passing test wearing an expected-failure label.
The fix, its replay measurement, and the caution that the obvious one-line
version makes the visible symptom *worse* are in
`docs/fidelity/pending-engine-fixes/README.md`.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.control import SimDeliverablePayload
from core.events.documents import DocumentCreatedPayload, DocumentRevisedPayload
from core.events.people import PersonRecordPayload
from simulation.gm.grounded import GroundedGm, TicketVocabulary

ROSTER = ("ana", "bo", "cy", "di", "ed")
# Comfortably past the roster size: the modulo only bites while there are
# fewer colleague documents than people, which is true for part of one
# morning and never again.
DOCUMENTS = 40


def _gm() -> GroundedGm:
    return GroundedGm(
        entity_for_person={f"per-{n}": n for n in ROSTER},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )


def _event(seq: int, tag: str, payload) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=seq * 60,
        tag=tag,
        source="gm",
        caused_by=None,
        payload=payload,
    )


async def _reviews_by_person(rounds: int = 60) -> dict[str, list[str]]:
    """Every document each person is handed to review, in order.

    The whole roster takes a deliverable turn each round, which is both
    what the firm does and what makes the simulation move. Two earlier
    versions of this helper drove one person alone and were wrong for the
    same underlying reason: the phase and the selection index are both
    counted off the *total version count in the world*, so a world nobody
    else is working in cannot advance. The first froze it completely by
    never recording the turn's result; the second recorded it and still
    deadlocked, because the phase that hands out no document also writes
    no version, so the counter stops on that phase and stays there. Both
    reported the *fixed* engine as still broken -- a test that cannot see
    a fix cannot see a regression either.
    """

    gm = _gm()
    seq = 0
    for name in ROSTER:
        seq += 1
        await gm.route(
            _event(
                seq,
                "person.record",
                PersonRecordPayload(
                    kind="person.record",
                    person_id=f"per-{name}",
                    name=name.title(),
                    title="Associate",
                    email_address=f"{name}@example.com",
                    department="Litigation",
                    affiliation="internal",
                    manager=None,
                    timezone="America/Los_Angeles",
                ),
            )
        )
    for index in range(DOCUMENTS):
        seq += 1
        await gm.route(
            _event(
                seq,
                "document.created",
                DocumentCreatedPayload(
                    kind="document.created",
                    document_id=f"doc-{index:06d}",
                    author=f"per-{ROSTER[index % len(ROSTER)]}",
                    title=f"Memo {index}",
                    path=f"engagements/matter-{index % 7}/memo-{index}.md",
                    location="repository",
                    content_format="markdown",
                    content=f"body of memo {index}",
                ),
            )
        )

    seen: dict[str, list[str]] = {name: [] for name in ROSTER}
    revision = dict.fromkeys(range(DOCUMENTS), 1)
    for _ in range(rounds):
        for reviewer in ROSTER:
            seq += 1
            event = _event(
                seq,
                "sim.deliverable",
                SimDeliverablePayload(
                    kind="sim.deliverable", entity=reviewer, day="2026-01-05"
                ),
            )
            await gm.route(event)
            spec = await gm.action_spec_for(reviewer, event)
            if not spec.revise_document_id:
                continue
            if spec.as_review:
                seen[reviewer].append(spec.revise_document_id)
            index = int(spec.revise_document_id.removeprefix("doc-"))
            revision[index] += 1
            seq += 1
            await gm.route(
                _event(
                    seq,
                    "document.revised",
                    DocumentRevisedPayload(
                        kind="document.revised",
                        document_id=spec.revise_document_id,
                        revision=revision[index],
                        author=f"per-{reviewer}",
                        content=f"body of memo {index}, rev {revision[index]}",
                        change_summary="reviewed",
                    ),
                )
            )
    return seen


async def test_the_branch_fires_at_all() -> None:
    """Guard the guard.

    If no deliverable ever reaches the review phase, the assertion below
    holds over an empty list and reports a fixed defect that is merely an
    unexercised one.
    """

    handed = await _reviews_by_person()
    assert any(handed.values()), "no review was ever handed out"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="grounded.py:770 indexes on the roster offset, which never changes; "
    "fix is pending v8, see pending-engine-fixes",
)
async def test_a_reviewer_is_handed_more_than_one_document() -> None:
    targets = (await _reviews_by_person())["ana"]
    assert len(set(targets)) > 1, (
        f"{len(targets)} reviews, all of {set(targets)}. The selection index "
        "does not advance, so this person reviews one file for the life of "
        "the firm."
    )


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="same defect, across the roster"
)
async def test_the_firm_reviews_more_than_one_document_per_person() -> None:
    """The population form, which is what the record actually shows.

    One person stuck on one file could be a quirk of their position in the
    list. Every person stuck on their own file is the rule computing a
    constant, and it is what 17-of-451 looks like from inside.
    """

    handed = await _reviews_by_person()
    total = {t for targets in handed.values() for t in targets}
    assert len(total) > len(ROSTER), (
        f"{len(ROSTER)} people between them reviewed {len(total)} of "
        f"{DOCUMENTS} documents"
    )

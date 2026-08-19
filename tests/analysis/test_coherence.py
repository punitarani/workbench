"""Contradictions must fail; ambiguities must not.

The split is the point. A record that says a ticket left `review` when it
was in `in-progress` cannot be graded — the answer depends on which of two
irreconcilable rows the agent read. A record with two documents of the same
name can be graded perfectly well, and is in fact more interesting than one
without; it just needs a key that can tell them apart.

A scan that treated those the same would either block a healthy world or
pass a broken one.
"""

import json
from pathlib import Path

import pytest

from analysis.coherence import check
from analysis.world_facts import load_world


def _event(seq: int, tag: str, payload: dict, time: int = 0) -> dict:
    return {
        "seq": seq,
        "event_id": f"evt-{seq:06d}",
        "time": time,
        "tag": tag,
        "source": "gm",
        "caused_by": None,
        "payload": {"kind": tag, **payload},
    }


def _write(tmp_path: Path, events: list[dict]) -> Path:
    path = tmp_path / "world.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path


BASE = [
    _event(
        0,
        "person.record",
        {
            "person_id": "per-a",
            "name": "Ada Reyes",
            "email_address": "ada@firm.example",
            "affiliation": "internal",
        },
    ),
    _event(
        1,
        "org.record",
        {"org_id": "org-x", "name": "Xenon Works", "category": "client"},
    ),
    _event(
        2,
        "ticket.created",
        {
            "ticket_id": "tkt-1",
            "actor": "per-a",
            "title": "Audit",
            "description": "",
            "requester": "per-a",
            "assignee": "per-a",
            "status": "Open",
            "priority": "Normal",
            "ticket_type": "engagement",
            "client_ref": "org-x",
            "fields": [],
        },
    ),
]


@pytest.fixture
def healthy(tmp_path: Path) -> Path:
    return _write(tmp_path, BASE)


class TestAHealthyWorldPasses:
    def test_nothing_is_reported(self, healthy: Path) -> None:
        found = check(load_world(healthy))
        assert found.ok
        assert found.contradictions == []
        assert found.dangling == []


class TestContradictionsBlock:
    def test_a_change_claiming_a_state_the_record_did_not_hold(
        self, tmp_path: Path
    ) -> None:
        """The exact shape the materializer refused in epoch-r10.

        Two people edit in one tick; both ground against the world as it is,
        and the second lands recording a move out of a status the record had
        already left. Four of these in 6,544 events made a whole 15-day run
        unusable, so this must fail loudly rather than round off.
        """

        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "ticket.updated",
                    {
                        "ticket_id": "tkt-1",
                        "actor": "per-a",
                        "changes": [
                            {"field": "status", "old": "Open", "new": "in-progress"}
                        ],
                    },
                    time=100,
                ),
                _event(
                    4,
                    "ticket.updated",
                    {
                        "ticket_id": "tkt-1",
                        "actor": "per-a",
                        "changes": [
                            {"field": "status", "old": "review", "new": "done"}
                        ],
                    },
                    time=200,
                ),
            ],
        )
        found = check(load_world(world))
        assert not found.ok
        assert any("claims it was 'review'" in c for c in found.contradictions)

    def test_a_chain_that_joins_is_accepted(self, tmp_path: Path) -> None:
        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "ticket.updated",
                    {
                        "ticket_id": "tkt-1",
                        "actor": "per-a",
                        "changes": [
                            {"field": "status", "old": "Open", "new": "in-progress"}
                        ],
                    },
                    time=100,
                ),
                _event(
                    4,
                    "ticket.updated",
                    {
                        "ticket_id": "tkt-1",
                        "actor": "per-a",
                        "changes": [
                            {"field": "status", "old": "in-progress", "new": "review"}
                        ],
                    },
                    time=200,
                ),
            ],
        )
        assert check(load_world(world)).ok

    def test_case_alone_is_not_a_contradiction(self, tmp_path: Path) -> None:
        """The seed writes `Open`; the personas write `open`.

        Both name the same state, and a scan that called that a defect would
        block every world this engine produces.
        """

        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "ticket.updated",
                    {
                        "ticket_id": "tkt-1",
                        "actor": "per-a",
                        "changes": [
                            {"field": "status", "old": "open", "new": "in-progress"}
                        ],
                    },
                    time=100,
                ),
            ],
        )
        assert check(load_world(world)).ok

    def test_a_repeated_revision_number(self, tmp_path: Path) -> None:
        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "document.created",
                    {
                        "document_id": "doc-1",
                        "author": "per-a",
                        "title": "Memo",
                        "path": "/audit/memo.md",
                        "location": "repository",
                        "content_format": "markdown",
                        "content": "x",
                    },
                ),
                _event(
                    4,
                    "document.revised",
                    {
                        "document_id": "doc-1",
                        "revision": 2,
                        "author": "per-a",
                        "content": "y",
                    },
                ),
                _event(
                    5,
                    "document.revised",
                    {
                        "document_id": "doc-1",
                        "revision": 2,
                        "author": "per-a",
                        "content": "z",
                    },
                ),
            ],
        )
        found = check(load_world(world))
        assert not found.ok
        assert any("revisions [1, 2, 2]" in c for c in found.contradictions)


class TestDanglingReferencesBlock:
    def test_time_logged_to_no_such_engagement(self, tmp_path: Path) -> None:
        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "work.time.logged",
                    {
                        "person_id": "per-a",
                        "ticket_id": "tkt-nope",
                        "minutes": 30,
                        "note": "",
                        "rate_cents": 1000,
                        "billable": True,
                    },
                ),
            ],
        )
        found = check(load_world(world))
        assert not found.ok
        assert any("tkt-nope" in d for d in found.dangling)

    def test_an_attachment_to_no_such_document(self, tmp_path: Path) -> None:
        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "email.message",
                    {
                        "message_id": "msg-1",
                        "thread_id": "thr-1",
                        "in_reply_to": None,
                        "sender": "per-a",
                        "to": ["per-a"],
                        "cc": [],
                        "subject": "s",
                        "body": "b",
                        "attachments": [
                            {
                                "filename": "f.docx",
                                "media_type": "x",
                                "document_id": "doc-nope",
                            }
                        ],
                    },
                ),
            ],
        )
        found = check(load_world(world))
        assert not found.ok
        assert any("doc-nope" in d for d in found.dangling)


class TestMisbookedTime:
    """A little is a firm; a lot is a world three tasks cannot be graded on.

    Measured on two recordings of the same firm: the ten-day world booked
    164 of one engagement's 200 entries to Kestrel 401(k) work on a
    Northwind *software* diligence matter — 20.7% of all client time — while
    the next recording, on the fixed engine, ran 0.8%. The threshold sits
    between those, so the first is refused and the second is not.
    """

    def _world(self, tmp_path: Path, notes: list[str]) -> Path:
        events = list(BASE)
        events.append(
            _event(
                3,
                "org.record",
                {"org_id": "org-y", "name": "Yarrow Freight", "category": "client"},
            )
        )
        for index, note in enumerate(notes):
            events.append(
                _event(
                    4 + index,
                    "work.time.logged",
                    {
                        "person_id": "per-a",
                        "ticket_id": "tkt-1",
                        "minutes": 30,
                        "note": note,
                        "rate_cents": 1000,
                        "billable": True,
                    },
                )
            )
        return _write(tmp_path, events)

    def test_notes_that_match_the_engagement_pass(self, tmp_path: Path) -> None:
        world = self._world(tmp_path, ["Xenon Works audit fieldwork"] * 10)
        found = check(load_world(world))
        assert found.misbooked == 0
        assert found.ok

    def test_a_stray_entry_is_realism(self, tmp_path: Path) -> None:
        notes = ["Xenon Works audit fieldwork"] * 39 + ["Yarrow Freight query"]
        found = check(load_world(self._world(tmp_path, notes)))
        assert found.misbooked == 1
        assert found.misbooked_share == 0.025
        assert found.ok, "one entry in forty is a firm, not a defect"

    def test_an_engagement_full_of_another_client_blocks(self, tmp_path: Path) -> None:
        notes = ["Xenon Works audit"] * 4 + ["Yarrow Freight 401(k) census"] * 6
        found = check(load_world(self._world(tmp_path, notes)))
        assert found.misbooked == 6
        assert not found.ok
        assert "MISBOOKED" in found.report()

    def test_a_note_naming_nobody_is_not_counted_against_it(
        self, tmp_path: Path
    ) -> None:
        """Half the firm's notes name no client at all, and must not count.

        Otherwise "Reviewed the engagement letter" would read as a
        mis-booking and every world would fail.
        """

        notes = ["Reviewed the engagement letter"] * 9 + ["Yarrow Freight query"]
        found = check(load_world(self._world(tmp_path, notes)))
        assert found.misbooked == 1
        assert found.time_entries == 10


class TestAmbiguitiesAreMaterialNotDefects:
    def test_two_documents_sharing_a_title_do_not_block(self, tmp_path: Path) -> None:
        """The collision that capped a solver at 0.976 — and is now a task.

        It must be reported, so a task can be built on it deliberately, and
        it must not fail the build, because a firm with two files of the same
        name is a realistic firm.
        """

        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "document.created",
                    {
                        "document_id": "doc-1",
                        "author": "per-a",
                        "title": "Single Audit Playbook",
                        "path": "/audit/a.md",
                        "location": "repository",
                        "content_format": "markdown",
                        "content": "x",
                    },
                ),
                _event(
                    4,
                    "document.created",
                    {
                        "document_id": "doc-2",
                        "author": "per-a",
                        "title": "Single Audit Playbook",
                        "path": "/tax/b.md",
                        "location": "repository",
                        "content_format": "markdown",
                        "content": "y",
                    },
                ),
            ],
        )
        found = check(load_world(world))
        assert found.ok, "a duplicate title is material, not a defect"
        assert any("Single Audit Playbook" in a for a in found.ambiguities)

    def test_a_shared_surname_is_reported(self, tmp_path: Path) -> None:
        world = _write(
            tmp_path,
            BASE
            + [
                _event(
                    3,
                    "person.record",
                    {
                        "person_id": "per-b",
                        "name": "Bo Reyes",
                        "email_address": "bo@firm.example",
                        "affiliation": "internal",
                    },
                ),
            ],
        )
        found = check(load_world(world))
        assert found.ok
        assert any("Reyes" in a for a in found.ambiguities)

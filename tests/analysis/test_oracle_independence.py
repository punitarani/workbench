"""The independence check must fail on the defects it was built to catch.

A verifier that only ever passes is indistinguishable from one that does
nothing, and this project has already shipped one of those: an
``unserved_tables`` gate that stayed green with the whole clio server
stashed out. So every case here injects a defect into the oracle and
asserts the check notices — the two real ones first, because those both
reached paid rollouts before anyone spotted them.

The world here is hand-built and tiny. That is deliberate: the recorded
epochs live under ``out/`` and are not committed, so a test that needed one
would skip in CI and prove nothing there.
"""

import json
import sys
from pathlib import Path

import pytest

from analysis.world_facts import load_world

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "datasets" / "ashgrove"))

from verify_oracle import (  # noqa: E402
    _rows,
    check_time_allocation,
    check_work_product_review,
)


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


@pytest.fixture
def world(tmp_path: Path) -> Path:
    """Two people, one engagement, four time entries, two documents.

    The entries are chosen so the two ways of totalling hours disagree:
    each is 25 minutes, which is 0.4166… hours and rounds to 0.42, so four
    rounded rows sum to 1.68 against 1.67 from the seconds. That is the
    same shape as the firm's 817.27-against-817.23, in miniature.
    """

    events = [
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
            "person.record",
            {
                "person_id": "per-b",
                "name": "Bo Nguyen",
                "email_address": "bo@firm.example",
                "affiliation": "internal",
            },
        ),
        _event(
            2,
            "person.record",
            {
                "person_id": "per-c",
                "name": "Cy Okafor",
                "email_address": "cy@client.example",
                "affiliation": "external",
                "department": "Client",
            },
        ),
        _event(
            3,
            "org.record",
            {"org_id": "org-x", "name": "Xenon Works", "category": "client"},
        ),
        _event(
            4,
            "ticket.created",
            {
                "ticket_id": "tkt-1",
                "actor": "per-a",
                "title": "Audit",
                "description": "",
                "requester": "per-c",
                "assignee": "per-a",
                "status": "Open",
                "priority": "Normal",
                "ticket_type": "engagement",
                "client_ref": "org-x",
                "fields": [],
            },
        ),
    ]
    seq = 5
    for person in ("per-a", "per-b"):
        for _ in range(2):
            events.append(
                _event(
                    seq,
                    "work.time.logged",
                    {
                        "person_id": person,
                        "ticket_id": "tkt-1",
                        "minutes": 25,
                        "note": "",
                        "rate_cents": 1_000,
                        "billable": True,
                    },
                )
            )
            seq += 1
    # Two documents with the same title in different workspaces: the exact
    # collision that capped work-product-review's own solver at 0.976.
    for index, workspace in enumerate(("audit", "tax"), start=1):
        events.append(
            _event(
                seq,
                "document.created",
                {
                    "document_id": f"doc-{index}",
                    "author": "per-a",
                    "title": "Single Audit Playbook",
                    "path": f"/{workspace}/playbook-{index}.md",
                    "location": "repository",
                    "content_format": "markdown",
                    "content": "x",
                },
            )
        )
        seq += 1

    path = tmp_path / "world.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path


def _allocation_oracle() -> dict:
    return {
        "entries_total": 4,
        "pairs": 2,
        "total_hours": 1.67,
        "total_billable_hours": 1.67,
        "total_fees_dollars": 16.67,
        "busiest_person": "Ada Reyes",
        "busiest_engagement": "00001-XenonWorks",
        "allocations": [
            {
                "person": "Ada Reyes",
                "engagement": "00001-XenonWorks",
                "entries": 2,
                "hours": 0.83,
                "billable_hours": 0.83,
                "fees_dollars": 8.33,
            },
            {
                "person": "Bo Nguyen",
                "engagement": "00001-XenonWorks",
                "entries": 2,
                "hours": 0.83,
                "billable_hours": 0.83,
                "fees_dollars": 8.33,
            },
        ],
    }


class TestTheCheckAgreesWithAHealthyOracle:
    def test_a_correct_oracle_raises_nothing(self, world: Path) -> None:
        assert check_time_allocation(load_world(world), _allocation_oracle()) == []


class TestTheCheckCatchesTheDefectsThatReachedRollouts:
    def test_totals_summed_from_rounded_rows(self, world: Path) -> None:
        """The 0.816: 1.66 from the rounded rows, 1.67 from the seconds."""

        oracle = _allocation_oracle()
        oracle["total_hours"] = round(sum(r["hours"] for r in oracle["allocations"]), 2)
        assert oracle["total_hours"] != 1.67
        problems = check_time_allocation(load_world(world), oracle)
        assert any("total_hours" in p for p in problems), problems

    def test_the_tie_break_follows_the_instruction_not_max(self, world: Path) -> None:
        """Ada and Bo log identical hours, so the tie-break decides the row.

        The instruction says take the *earlier* name. The solver said
        ``max(rows, key=(hours, person, ...))``, which takes the later one —
        a contradiction no rollout could have surfaced, because no two rows
        tie at the top of the recorded world. This fixture makes them tie.
        """

        facts = load_world(world)
        rows = _allocation_oracle()["allocations"]
        assert rows[0]["hours"] == rows[1]["hours"], "the fixture must tie"

        assert check_time_allocation(facts, _allocation_oracle()) == []

        later = _allocation_oracle()
        later["busiest_person"] = "Bo Nguyen"
        assert any("busiest_person" in p for p in check_time_allocation(facts, later))

    def test_two_documents_sharing_a_title(self, world: Path) -> None:
        """The 0.976 ceiling: a title-only key cannot tell them apart."""

        rows = [
            {"document": "Single Audit Playbook", "workspace": "audit"},
            {"document": "Single Audit Playbook", "workspace": "tax"},
        ]
        problems: list[str] = []
        _rows("documents", rows, rows, lambda r: r["document"], problems)
        assert any("collapse" in p for p in problems), problems

        # The composite key that fixed it must *not* fire.
        clean: list[str] = []
        _rows("documents", rows, rows, lambda r: (r["document"], r["workspace"]), clean)
        assert clean == []


class TestTheCheckCatchesOrdinaryCorruption:
    def test_one_wrong_figure_among_the_rows(self, world: Path) -> None:
        oracle = _allocation_oracle()
        oracle["allocations"][1]["fees_dollars"] += 1.0
        problems = check_time_allocation(load_world(world), oracle)
        assert any("fees_dollars" in p for p in problems), problems

    def test_a_missing_row(self, world: Path) -> None:
        oracle = _allocation_oracle()
        oracle["allocations"].pop()
        oracle["pairs"] = 1
        problems = check_time_allocation(load_world(world), oracle)
        assert any("the log has" in p for p in problems), problems

    def test_an_invented_row(self, world: Path) -> None:
        oracle = _allocation_oracle()
        oracle["allocations"].append(
            {
                "person": "Nobody At All",
                "engagement": "00001-XenonWorks",
                "entries": 1,
                "hours": 1.0,
                "billable_hours": 1.0,
                "fees_dollars": 1.0,
            }
        )
        oracle["pairs"] = 3
        problems = check_time_allocation(load_world(world), oracle)
        assert any("the log does not" in p for p in problems), problems

    def test_a_wrong_scalar(self, world: Path) -> None:
        oracle = _allocation_oracle()
        oracle["busiest_person"] = "Bo Nguyen"
        problems = check_time_allocation(load_world(world), oracle)
        assert any("busiest_person" in p for p in problems), problems


class TestDocumentDerivation:
    def test_review_and_delivery_are_read_from_the_chain(self, world: Path) -> None:
        """Nothing was revised and nothing was mailed, so both are false.

        Worth asserting because this is precisely the degenerate shape the
        ten-day world produced — 34 documents, 0 reviewed — and a check that
        could not express it would hide the next one.
        """

        facts = load_world(world)
        oracle = {
            "documents_total": 2,
            "reviewed_count": 0,
            "unreviewed_count": 2,
            "reached_client_count": 0,
            "never_attached_count": 2,
            "documents": [
                {
                    "document_number": 1,
                    "document": "Single Audit Playbook",
                    "workspace": "audit",
                    "author": "Ada Reyes",
                    "versions": 1,
                    "reviewed": False,
                    "reached_client": False,
                },
                {
                    "document_number": 2,
                    "document": "Single Audit Playbook",
                    "workspace": "tax",
                    "author": "Ada Reyes",
                    "versions": 1,
                    "reviewed": False,
                    "reached_client": False,
                },
            ],
        }
        assert check_work_product_review(facts, oracle) == []

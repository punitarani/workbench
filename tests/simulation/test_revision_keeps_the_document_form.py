"""Working a document forward must not change what kind of file it is.

Creation has always validated that a document declaring `spreadsheet`
really parses as one — the rejection is instructive, and the persona
retries. Revision validated nothing, and the revise path drafts prose.

So a workbook worked forward came back as text, kept its `spreadsheet`
declaration, and materialized into the file room as a `.txt` whose body
was a broken JSON fragment. Ten of fifty-two documents in one recorded
world landed that way. Nothing failed at the time. An agent asked to
open the workbook would have found a text file, and the score would have
read as a model failure.

This is the "loud failure" rule applied to the one path that was quiet:
a rejection the actor can see and retry, rather than a corruption
discovered by whatever finally reads the surface.
"""

import json

import pytest

from core.artifacts import SpreadsheetContent
from simulation.gm.grounded import IntentRejection, _reject_unless_parsable

_WORKBOOK = SpreadsheetContent.model_validate(
    {
        "sheets": [
            {
                "name": "Summary",
                "columns": ["Item", "Amount"],
                "rows": [["Opening", "100"], ["Closing", "140"]],
            }
        ]
    }
).model_dump_json()


def test_a_real_workbook_passes() -> None:
    _reject_unless_parsable("spreadsheet", _WORKBOOK, "wip.xlsx")


def test_prose_in_a_workbooks_place_is_rejected() -> None:
    with pytest.raises(IntentRejection) as caught:
        _reject_unless_parsable(
            "spreadsheet",
            "I have updated the tie-out and cleared two review notes.",
            "wip.xlsx",
        )
    # The rejection has to tell the persona what to do instead, or it is
    # just a failure with extra steps.
    assert "structured JSON" in str(caught.value)
    assert "wip.xlsx" in str(caught.value)


def test_the_malformation_that_actually_occurred_is_rejected() -> None:
    """The recorded corruption was not arbitrary text — it was a sheet
    array closed early and then continued, which is JSON-shaped enough to
    fool a check that only looks for a leading brace."""

    broken = (
        '{"sheets":[{"name":"Summary","columns":["A"],"rows":[["1"]]}],'
        '{"name":"Census","columns":["B"],"rows":[]}]}'
    )
    with pytest.raises((json.JSONDecodeError, IntentRejection)):
        _reject_unless_parsable("spreadsheet", broken, "tie-out.xlsx")


def test_markdown_accepts_anything() -> None:
    """Prose is prose. Only the structured forms have a shape to violate."""

    _reject_unless_parsable("markdown", "anything at all", "note.md")


@pytest.mark.parametrize("form", ["formatted", "slides"])
def test_every_structured_form_is_covered(form: str) -> None:
    """Guard the guard: a validator wired only for spreadsheets would pass
    every test above while leaving decks and documents corruptible."""

    with pytest.raises(IntentRejection):
        _reject_unless_parsable(form, "just some prose", f"thing.{form}")

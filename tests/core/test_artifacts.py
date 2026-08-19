"""Structured document content: canonical JSON in, the same model out.

Determinism lives here — rendered bytes (xlsx/docx/pdf) are derived
artifacts and never part of any byte-identity guarantee.
"""

import pytest
from pydantic import ValidationError

from core.artifacts import (
    FormattedDocument,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    SpreadsheetContent,
    SpreadsheetSheet,
    TableBlock,
    parse_formatted,
    parse_spreadsheet,
)


def sample_sheet() -> SpreadsheetContent:
    return SpreadsheetContent(
        sheets=(
            SpreadsheetSheet(
                name="Fees",
                columns=("Matter", "Hours", "Rate", "Billable"),
                rows=(
                    ("Vantage NDA", 3.5, 45000, True),
                    ("Harbor lease", 2, 52500, False),
                    ("Conflicts check", None, None, True),
                ),
            ),
        )
    )


def sample_document() -> FormattedDocument:
    return FormattedDocument(
        blocks=(
            HeadingBlock(level=1, text="Engagement Letter"),
            ParagraphBlock(text="This letter confirms the scope of work."),
            HeadingBlock(level=2, text="Fees"),
            ListBlock(ordered=True, items=("Fixed fee review", "Hourly overflow")),
            TableBlock(
                columns=("Item", "Amount"),
                rows=(("Retainer", "$5,000"), ("Cap", "$12,000")),
            ),
        )
    )


def test_spreadsheet_round_trips_canonically() -> None:
    content = sample_sheet()
    encoded = content.canonical_json()
    assert parse_spreadsheet(encoded) == content
    assert parse_spreadsheet(encoded).canonical_json() == encoded


def test_formatted_document_round_trips_canonically() -> None:
    document = sample_document()
    encoded = document.canonical_json()
    assert parse_formatted(encoded) == document
    assert parse_formatted(encoded).canonical_json() == encoded


def test_ragged_rows_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SpreadsheetSheet(
            name="Bad",
            columns=("A", "B"),
            rows=(("only-one",),),
        )


def test_parse_rejects_garbage_with_a_clear_error() -> None:
    with pytest.raises(ValidationError):
        parse_spreadsheet("not json at all")
    with pytest.raises(ValidationError):
        parse_formatted('{"blocks": [{"kind": "hologram"}]}')

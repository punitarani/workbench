"""Renderers for the v2 formats: formulas that compute, decks that open.

A file that writes but does not reopen is a failure, so every case here
reads the artifact back with an independent library rather than trusting
that the write returned cleanly.
"""

from pathlib import Path

import pytest

from artifacts.render import render_document
from core.artifacts import (
    Formula,
    Slide,
    SlideDeck,
    SpreadsheetContent,
    SpreadsheetSheet,
    TableBlock,
)

openpyxl = pytest.importorskip("openpyxl")
pptx = pytest.importorskip("pptx")


class TestFormulaCells:
    def test_formula_lands_as_a_real_formula(self, tmp_path: Path) -> None:
        content = SpreadsheetContent(
            sheets=(
                SpreadsheetSheet(
                    name="CAM",
                    columns=("Item", "Amount"),
                    rows=(
                        ("Admin overhead", 2100),
                        ("Utilities", 1225),
                        ("Total", Formula(expression="=SUM(B2:B3)")),
                    ),
                ),
            )
        )
        target = tmp_path / "cam.xlsx"
        outcome = render_document("spreadsheet", content.canonical_json(), target)
        assert outcome.skipped is None

        workbook = openpyxl.load_workbook(target)
        sheet = workbook["CAM"]
        assert sheet["B2"].value == 2100
        # Read back as a formula, not as a frozen number or a literal string.
        assert sheet["B4"].value == "=SUM(B2:B3)"
        assert sheet["B4"].data_type == "f"

    def test_cross_sheet_reference(self, tmp_path: Path) -> None:
        content = SpreadsheetContent(
            sheets=(
                SpreadsheetSheet(name="Detail", columns=("Amount",), rows=((500,),)),
                SpreadsheetSheet(
                    name="Summary",
                    columns=("Tie-out",),
                    rows=((Formula(expression="=Detail!A2"),),),
                ),
            )
        )
        target = tmp_path / "tieout.xlsx"
        render_document("spreadsheet", content.canonical_json(), target)
        workbook = openpyxl.load_workbook(target)
        assert workbook["Summary"]["A2"].value == "=Detail!A2"

    def test_a_formula_must_start_with_equals(self) -> None:
        with pytest.raises(ValueError):
            Formula(expression="SUM(B2:B3)")


class TestSlideDecks:
    def _deck(self) -> SlideDeck:
        return SlideDeck(
            slides=(
                Slide(
                    title="Q1 close — Kestrel",
                    bullets=("Close landed on the 5th", "One open CAM item"),
                    notes="Lead with the timeline.",
                ),
                Slide(
                    title="Variance detail",
                    table=TableBlock(
                        kind="table",
                        columns=("Line", "Variance"),
                        rows=(("Admin overhead", "2,100"), ("Utilities", "1,225")),
                    ),
                ),
            )
        )

    def test_deck_opens_with_its_content(self, tmp_path: Path) -> None:
        target = tmp_path / "close.pptx"
        outcome = render_document("slides", self._deck().canonical_json(), target)
        assert outcome.skipped is None
        assert outcome.path == target

        presentation = pptx.Presentation(str(target))
        assert len(presentation.slides) == 2
        first = presentation.slides[0]
        assert first.shapes.title.text == "Q1 close — Kestrel"
        body = [
            shape.text_frame.text
            for shape in first.shapes
            if shape.has_text_frame and shape != first.shapes.title
        ]
        assert any("Close landed on the 5th" in text for text in body)
        assert first.notes_slide.notes_text_frame.text == "Lead with the timeline."

    def test_table_slide_carries_its_grid(self, tmp_path: Path) -> None:
        target = tmp_path / "variance.pptx"
        render_document("slides", self._deck().canonical_json(), target)
        presentation = pptx.Presentation(str(target))
        tables = [
            shape.table for shape in presentation.slides[1].shapes if shape.has_table
        ]
        assert len(tables) == 1
        table = tables[0]
        assert table.cell(0, 0).text == "Line"
        assert table.cell(1, 1).text == "2,100"

    def test_prose_in_a_deck_falls_back_and_records_the_skip(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "notes.pptx"
        outcome = render_document("slides", "Just some prose, not a deck.", target)
        assert outcome.path == tmp_path / "notes.txt"
        assert "did not parse" in (outcome.skipped or "")
        assert outcome.path.read_text() == "Just some prose, not a deck."

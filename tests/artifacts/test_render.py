"""Renderers turn structured content into real office files.

Openability is the contract; byte stability is explicitly not.
"""

from pathlib import Path

from workbench.artifacts.render import RenderOutcome, render_document
from workbench.core.artifacts import (
    FormattedDocument,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    SpreadsheetContent,
    SpreadsheetSheet,
    TableBlock,
)


def sheet_content() -> str:
    return SpreadsheetContent(
        sheets=(
            SpreadsheetSheet(
                name="Fees",
                columns=("Matter", "Hours"),
                rows=(("Vantage NDA", 3.5), ("Harbor lease", 2)),
            ),
        )
    ).canonical_json()


def formatted_content() -> str:
    return FormattedDocument(
        blocks=(
            HeadingBlock(level=1, text="Engagement Letter"),
            ParagraphBlock(text="Scope of work below."),
            ListBlock(ordered=False, items=("Review", "Redline")),
            TableBlock(columns=("Item", "Amount"), rows=(("Retainer", "$5,000"),)),
        )
    ).canonical_json()


def test_markdown_passes_through(tmp_path: Path) -> None:
    outcome = render_document(
        "markdown", "# Hello", tmp_path / "note.md"
    )
    assert outcome == RenderOutcome(path=tmp_path / "note.md", skipped=None)
    assert (tmp_path / "note.md").read_text(encoding="utf-8") == "# Hello"


def test_spreadsheet_renders_openable_xlsx(tmp_path: Path) -> None:
    from openpyxl import load_workbook

    outcome = render_document("spreadsheet", sheet_content(), tmp_path / "fees.xlsx")
    assert outcome.skipped is None
    workbook = load_workbook(outcome.path)
    sheet = workbook["Fees"]
    assert [cell.value for cell in sheet[1]] == ["Matter", "Hours"]
    assert [cell.value for cell in sheet[2]] == ["Vantage NDA", 3.5]
    assert [cell.value for cell in sheet[3]] == ["Harbor lease", 2]


def test_formatted_renders_openable_docx(tmp_path: Path) -> None:
    from docx import Document

    outcome = render_document(
        "formatted", formatted_content(), tmp_path / "letter.docx"
    )
    assert outcome.skipped is None
    document = Document(str(outcome.path))
    texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    assert texts[0] == "Engagement Letter"
    assert "Scope of work below." in texts
    table = document.tables[0]
    assert table.rows[0].cells[0].text == "Item"
    assert table.rows[1].cells[1].text == "$5,000"


def test_pdf_without_soffice_records_a_skip(
    tmp_path: Path, monkeypatch
) -> None:
    import workbench.artifacts.render as render

    monkeypatch.setattr(render.shutil, "which", lambda name: None)
    outcome = render_document(
        "formatted", formatted_content(), tmp_path / "letter.pdf"
    )
    # The content still lands — as the docx it was built from — and the
    # skip is recorded rather than silently swallowed.
    assert outcome.path == tmp_path / "letter.docx"
    assert outcome.skipped is not None and "soffice" in outcome.skipped
    assert outcome.path.exists()

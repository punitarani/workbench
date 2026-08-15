"""Render structured document content into real office files.

Consumed by environment materialization only — the simulation never sees
rendered bytes. Requires the ``artifacts`` extra (openpyxl, python-docx);
PDF conversion additionally uses LibreOffice's ``soffice`` when installed
and records a skip when it is not.
"""

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from workbench.core.artifacts import (
    FormattedDocument,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    SpreadsheetContent,
    TableBlock,
    parse_formatted,
    parse_spreadsheet,
)


class RenderOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    # Human-readable reason when the requested form could not be produced
    # and a fallback was written instead. Never silently swallowed.
    skipped: str | None = None


def render_document(content_format: str, content: str, target: Path) -> RenderOutcome:
    """Write ``content`` to ``target`` in its real file form and return
    where it actually landed."""

    target.parent.mkdir(parents=True, exist_ok=True)
    match content_format:
        case "markdown":
            target.write_text(content, encoding="utf-8")
            return RenderOutcome(path=target)
        case "spreadsheet":
            try:
                parsed = parse_spreadsheet(content)
            except ValueError:
                return _raw_fallback(content_format, content, target)
            _render_xlsx(parsed, target)
            return RenderOutcome(path=target)
        case "formatted":
            try:
                document = parse_formatted(content)
            except ValueError:
                return _raw_fallback(content_format, content, target)
            if target.suffix.lower() == ".pdf":
                return _render_pdf(document, target)
            _render_docx(document, target)
            return RenderOutcome(path=target)
        case _:
            raise ValueError(f"unknown content format {content_format!r}")


def _raw_fallback(content_format: str, content: str, target: Path) -> RenderOutcome:
    """Authors sometimes declare a structured format but write prose; the
    record still deserves a file, so the raw text lands beside the intended
    name with the skip recorded."""

    fallback = target.with_suffix(".txt")
    fallback.write_text(content, encoding="utf-8")
    return RenderOutcome(
        path=fallback,
        skipped=(
            f"{target.name}: {content_format} content did not parse; "
            f"wrote raw text as {fallback.name}"
        ),
    )


def _render_xlsx(content: SpreadsheetContent, target: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet in content.sheets:
        worksheet = workbook.create_sheet(title=sheet.name)
        worksheet.append(list(sheet.columns))
        for row in sheet.rows:
            worksheet.append(list(row))
    workbook.save(target)


def _render_docx(document: FormattedDocument, target: Path) -> None:
    from docx import Document

    output = Document()
    for block in document.blocks:
        match block:
            case HeadingBlock():
                output.add_heading(block.text, level=block.level)
            case ParagraphBlock():
                output.add_paragraph(block.text)
            case ListBlock():
                style = "List Number" if block.ordered else "List Bullet"
                for item in block.items:
                    output.add_paragraph(item, style=style)
            case TableBlock():
                table = output.add_table(
                    rows=len(block.rows) + 1, cols=len(block.columns)
                )
                for column, name in enumerate(block.columns):
                    table.rows[0].cells[column].text = name
                for index, row in enumerate(block.rows, start=1):
                    for column, value in enumerate(row):
                        table.rows[index].cells[column].text = value
    output.save(str(target))


def _render_pdf(document: FormattedDocument, target: Path) -> RenderOutcome:
    intermediate = target.with_suffix(".docx")
    _render_docx(document, intermediate)
    soffice = shutil.which("soffice")
    if soffice is None:
        return RenderOutcome(
            path=intermediate,
            skipped=f"{target.name}: PDF conversion needs soffice "
            "(LibreOffice); wrote the docx instead",
        )
    subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(target.parent),
            str(intermediate),
        ],
        check=True,
        capture_output=True,
    )
    intermediate.unlink()
    return RenderOutcome(path=target)

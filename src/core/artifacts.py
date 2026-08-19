"""Structured document content.

The world log stores every document as text (``content: str``). For
realistic office files, the text is the canonical JSON of one of these
models and the payload's ``content_format`` names which one. Determinism
is defined over this JSON; rendered bytes (xlsx/docx/pdf) are derived
artifacts and never part of any byte-identity guarantee.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def canonical_json(self) -> str:
        """The deterministic wire form: field order is model order."""
        return self.model_dump_json()


class Formula(_Model):
    """A spreadsheet formula: the thing that makes a workpaper a workpaper.

    Stored as structure rather than a bare "=" string so the canonical JSON
    stays unambiguous and a renderer can tell a formula from a person who
    happened to start a sentence with an equals sign.
    """

    kind: Literal["formula"] = "formula"
    expression: str = Field(min_length=1)

    @model_validator(mode="after")
    def _leading_equals(self) -> Formula:
        if not self.expression.startswith("="):
            raise ValueError("a formula expression starts with '='")
        return self


Cell = str | int | float | bool | None | Formula


class SpreadsheetSheet(_Model):
    name: str
    columns: tuple[str, ...] = Field(min_length=1)
    rows: tuple[tuple[Cell, ...], ...] = ()

    @model_validator(mode="after")
    def _rows_match_columns(self) -> SpreadsheetSheet:
        for index, row in enumerate(self.rows):
            if len(row) != len(self.columns):
                raise ValueError(
                    f"row {index} has {len(row)} cells; sheet {self.name!r} "
                    f"has {len(self.columns)} columns"
                )
        return self


class SpreadsheetContent(_Model):
    sheets: tuple[SpreadsheetSheet, ...] = Field(min_length=1)


class HeadingBlock(_Model):
    kind: Literal["heading"] = "heading"
    level: int = Field(ge=1, le=6)
    text: str


class ParagraphBlock(_Model):
    kind: Literal["paragraph"] = "paragraph"
    text: str


class ListBlock(_Model):
    kind: Literal["list"] = "list"
    ordered: bool
    items: tuple[str, ...] = Field(min_length=1)


class TableBlock(_Model):
    kind: Literal["table"] = "table"
    columns: tuple[str, ...] = Field(min_length=1)
    rows: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def _rows_match_columns(self) -> TableBlock:
        for index, row in enumerate(self.rows):
            if len(row) != len(self.columns):
                raise ValueError(
                    f"table row {index} has {len(row)} cells for "
                    f"{len(self.columns)} columns"
                )
        return self


Block = Annotated[
    HeadingBlock | ParagraphBlock | ListBlock | TableBlock,
    Field(discriminator="kind"),
]


class FormattedDocument(_Model):
    blocks: tuple[Block, ...] = Field(min_length=1)


class Slide(_Model):
    """One slide: a title, body bullets, an optional table, and notes.

    Deliberately narrow. A deck a professional actually builds for a
    client meeting is a title and a handful of claims, sometimes a table
    of numbers — not a design surface.
    """

    title: str
    bullets: tuple[str, ...] = ()
    table: TableBlock | None = None
    notes: str = ""


class SlideDeck(_Model):
    slides: tuple[Slide, ...] = Field(min_length=1)


def parse_spreadsheet(content: str) -> SpreadsheetContent:
    return SpreadsheetContent.model_validate_json(content)


def parse_formatted(content: str) -> FormattedDocument:
    return FormattedDocument.model_validate_json(content)


def parse_slides(content: str) -> SlideDeck:
    return SlideDeck.model_validate_json(content)

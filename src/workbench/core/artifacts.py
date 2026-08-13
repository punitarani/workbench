"""Structured document content.

The world log stores every document as text (``content: str``). For
realistic office files, the text is the canonical JSON of one of these
models and the payload's ``content_format`` names which one. Determinism
is defined over this JSON; rendered bytes (xlsx/docx/pdf) are derived
artifacts and never part of any byte-identity guarantee.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Cell = str | int | float | bool | None


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def canonical_json(self) -> str:
        """The deterministic wire form: field order is model order."""
        return self.model_dump_json()


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


def parse_spreadsheet(content: str) -> SpreadsheetContent:
    return SpreadsheetContent.model_validate_json(content)


def parse_formatted(content: str) -> FormattedDocument:
    return FormattedDocument.model_validate_json(content)

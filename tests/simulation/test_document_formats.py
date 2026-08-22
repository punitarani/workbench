"""Format-aware document creation: declare a format, and mean it."""

import pytest
from pydantic import ValidationError

from core.artifacts import (
    Formula,
    Slide,
    SlideDeck,
    SpreadsheetContent,
    SpreadsheetSheet,
)
from core.intents import DocumentCreateSpec
from simulation.gm.grounded import IntentRejection, _validated_format


def _spreadsheet() -> str:
    return SpreadsheetContent(
        sheets=(
            SpreadsheetSheet(
                name="Rollforward",
                columns=("Account", "Balance"),
                rows=(("Cash", 1200), ("Total", Formula(expression="=SUM(B2:B2)"))),
            ),
        )
    ).canonical_json()


class TestDeclaredFormats:
    def test_the_format_must_be_stated(self) -> None:
        """There is no default, and that is the point.

        While `content_format` defaulted to markdown, every document the
        firm authored came out a .md file: the field could simply be
        omitted, so it always was. Making the author declare the form is
        what produces workbooks, memos, and decks.
        """

        with pytest.raises(ValidationError):
            DocumentCreateSpec(
                title="Notes", path="/firm/notes.md", content="Just prose."
            )

    def test_markdown_needs_no_parse(self) -> None:
        create = DocumentCreateSpec(
            title="Notes",
            path="/firm/notes.md",
            content="Just prose.",
            content_format="markdown",
        )
        assert _validated_format(create) == "markdown"

    def test_spreadsheet_content_passes(self) -> None:
        create = DocumentCreateSpec(
            title="WP",
            path="/clients/kestrel/rollforward.xlsx",
            content=_spreadsheet(),
            content_format="spreadsheet",
        )
        assert _validated_format(create) == "spreadsheet"

    def test_slides_content_passes(self) -> None:
        deck = SlideDeck(slides=(Slide(title="Close review", bullets=("On time",)),))
        create = DocumentCreateSpec(
            title="Deck",
            path="/clients/kestrel/close.pptx",
            content=deck.canonical_json(),
            content_format="slides",
        )
        assert _validated_format(create) == "slides"

    @pytest.mark.parametrize("declared", ["spreadsheet", "formatted", "slides"])
    def test_prose_in_a_structured_format_is_rejected_instructively(
        self, declared: str
    ) -> None:
        create = DocumentCreateSpec(
            title="Checklist",
            path="/firm/checklist.xlsx",
            content="**Monthly close checklist**\n\n- Tie out cash",
            content_format=declared,
        )
        with pytest.raises(IntentRejection) as caught:
            _validated_format(create)
        reason = caught.value.reason
        # Named in workplace words, not by the enum value. "spreadsheet"
        # and "structured JSON" are what the machine calls these; a
        # partner reading their own memory calls them a workbook and a
        # note. Cecile Marchand paraphrased the old wording into her
        # reflection as "the underlying content is not actually structured
        # JSON", which is not a sentence anyone at a law firm has said.
        assert {"spreadsheet": "workbook", "formatted": "document", "slides": "deck"}[
            declared
        ] in reason
        # And it still has to say what to do instead, the way the
        # thread-cap and unknown-ref rejections do.
        assert "note" in reason
        assert any(word in reason for word in ("rows", "headings", "slides"))
        assert "json" not in reason.lower()

    def test_a_spreadsheet_with_ragged_rows_is_rejected(self) -> None:
        create = DocumentCreateSpec(
            title="WP",
            path="/clients/kestrel/wp.xlsx",
            content='{"sheets":[{"name":"S","columns":["a","b"],"rows":[[1]]}]}',
            content_format="spreadsheet",
        )
        with pytest.raises(IntentRejection):
            _validated_format(create)

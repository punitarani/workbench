"""Format-aware document creation: declare a format, and mean it."""

import pytest

from workbench.core.artifacts import (
    Formula,
    Slide,
    SlideDeck,
    SpreadsheetContent,
    SpreadsheetSheet,
)
from workbench.core.intents import DocumentCreateSpec
from workbench.simulation.gm.grounded import IntentRejection, _validated_format


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
    def test_markdown_is_the_default_and_needs_no_parse(self) -> None:
        create = DocumentCreateSpec(
            title="Notes", path="/firm/notes.md", content="Just prose."
        )
        assert create.content_format == "markdown"
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
        assert declared in reason
        # The rejection has to tell the persona what to do instead, the way
        # the thread-cap and unknown-ref rejections do.
        assert "structured JSON" in reason and "markdown" in reason

    def test_a_spreadsheet_with_ragged_rows_is_rejected(self) -> None:
        create = DocumentCreateSpec(
            title="WP",
            path="/clients/kestrel/wp.xlsx",
            content='{"sheets":[{"name":"S","columns":["a","b"],"rows":[[1]]}]}',
            content_format="spreadsheet",
        )
        with pytest.raises(IntentRejection):
            _validated_format(create)

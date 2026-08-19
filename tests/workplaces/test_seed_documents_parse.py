"""A seeded document must be the form it declares, at build time.

Third instance of one defect class, so it becomes a gate rather than
another fix. A document declaring a structured format and containing
something else is rejected when a *persona* creates one, and now also
when a persona revises one. But a document placed in the world by its own
definition is checked by nothing at all — `SeedDocument.content` is a
string with a declared format beside it, and the first thing that reads
it for real is the renderer, at materialization, long after the world was
built.

What that costs: the renderer writes the raw bytes beside the intended
name with a `.txt` suffix, so the file room ends up holding a file that
claims to be a workbook and is not. Found exactly that way — a rate card
whose header row was folded into `rows` instead of being declared as
`columns`. It parsed as nothing, materialized as text, and every workbook
count in that world was off by one.

The floor this holds: **an invariant enforced at one entry point is not
enforced.** Creation, revision and seeding are three doors into the same
room.
"""

import importlib
import pkgutil

import pytest

from core.artifacts import parse_formatted, parse_slides, parse_spreadsheet
from simulation.workplace.spec import WorkplaceSpec

_PARSERS = {
    "spreadsheet": parse_spreadsheet,
    "formatted": parse_formatted,
    "slides": parse_slides,
}


def _specs() -> list[tuple[str, WorkplaceSpec]]:
    """Every workplace that can build a spec without a recording."""

    import workplaces

    found: list[tuple[str, WorkplaceSpec]] = []
    for module in pkgutil.iter_modules(workplaces.__path__):
        for suffix in ("epoch", "spec"):
            name = f"workplaces.{module.name}.{suffix}"
            try:
                loaded = importlib.import_module(name)
            except ModuleNotFoundError:
                continue
            builder = getattr(loaded, "epoch_spec", None)
            if callable(builder):
                found.append((name, builder(days=2)))
                continue
            for attribute in dir(loaded):
                value = getattr(loaded, attribute)
                if isinstance(value, WorkplaceSpec):
                    found.append((f"{name}.{attribute}", value))
    return found


SPECS = _specs()


def test_the_audit_found_workplaces_to_check() -> None:
    """Guard the guard: an import sweep that finds nothing passes
    vacuously, and this one walks a package tree that changes."""

    assert len(SPECS) >= 3, [name for name, _ in SPECS]


@pytest.mark.parametrize("named", SPECS, ids=lambda pair: pair[0])
def test_every_seed_document_parses_as_its_declared_format(
    named: tuple[str, WorkplaceSpec],
) -> None:
    name, spec = named
    broken = []
    for document in spec.seed_documents:
        parser = _PARSERS.get(document.content_format)
        if parser is None:  # markdown is prose; there is no shape to violate
            continue
        try:
            parser(document.content)
        except ValueError as error:
            broken.append(f"{document.path}: {str(error).splitlines()[0]}")
    assert not broken, (
        f"{name} seeds documents that do not parse as the format they "
        f"declare, so they will materialize as raw text claiming a form "
        f"they do not have: {broken}"
    )


def test_a_seeded_workbook_that_folds_its_header_is_caught() -> None:
    """The exact malformation that got through: a header row inside
    `rows` instead of a declared `columns`. It is valid JSON and reads
    correctly to a human, which is why nothing noticed."""

    import json

    folded = json.dumps(
        {
            "sheets": [
                {
                    "name": "Rates",
                    "rows": [["Timekeeper", "Rate"], ["A. Partner", 900]],
                }
            ]
        }
    )
    with pytest.raises(ValueError):
        parse_spreadsheet(folded)

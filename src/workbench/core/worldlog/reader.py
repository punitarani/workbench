from pathlib import Path

from pydantic import ValidationError

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.events import Event


def read_events(path: Path) -> list[Event]:
    events: list[Event] = []
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(Event.model_validate_json(stripped))
            except ValidationError as error:
                raise WorldLogIntegrityError(
                    f"{path}:{line_number} failed validation: {error}"
                ) from error
    return events

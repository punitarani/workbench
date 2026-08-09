"""Recover id-minter state from an existing log.

Scans every payload field whose value is exactly a minted id
(``prefix-NNNNNN``) and returns a minter whose counters continue after the
per-prefix maximum, so later segments can never collide with earlier ids.
Prose that merely mentions an id does not match: the pattern must cover the
whole field.
"""

import re
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.ids import IdMinter

_MINTED_ID = re.compile(r"^([a-z][a-z0-9-]*)-(\d{6})$")


def _scan(value: object, counters: dict[str, int]) -> None:
    match value:
        case str():
            matched = _MINTED_ID.match(value)
            if matched is not None:
                prefix, count = matched.group(1), int(matched.group(2))
                counters[prefix] = max(counters.get(prefix, 0), count)
        case dict():
            for item in value.values():
                _scan(item, counters)
        case list() | tuple():
            for item in value:
                _scan(item, counters)
        case _:
            pass


def minter_from_events(events: Sequence[Event]) -> IdMinter:
    counters: dict[str, int] = {}
    for event in events:
        _scan(event.payload.model_dump(mode="json"), counters)
    return IdMinter(counters=dict(sorted(counters.items())))

"""Hartwell & Marsh LLP: the Phase 2 four-month-history law firm.

A twelve-person firm with twelve clients and a populated outside world.
``build_genesis`` produces the time-zero event sequence; ``procedural_cast``
derives the background-traffic cast the chronicle generators consume.
"""

from workbench.workplaces.hartwell.genesis import (
    EPOCH_ISO,
    TIMEZONE,
    WINDOW,
    WORKPLACE_ID,
    HartwellGenesis,
    build_genesis,
    procedural_cast,
)

__all__ = [
    "EPOCH_ISO",
    "TIMEZONE",
    "WINDOW",
    "WORKPLACE_ID",
    "HartwellGenesis",
    "build_genesis",
    "procedural_cast",
]

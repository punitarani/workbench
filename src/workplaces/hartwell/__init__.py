"""Hartwell & Marsh LLP: the Phase 2 four-month-history law firm.

A twelve-person firm with twelve clients and a populated outside world.
``build_genesis`` produces the time-zero event sequence; ``procedural_cast``
derives the background-traffic cast and ``day_profile`` the shape of each
calendar day — full workday, reduced weekend, or observed holiday — that
the chronicle generators consume. ``VOICE`` carries the firm's register.
"""

from workplaces.hartwell.genesis import (
    EPOCH_ISO,
    FEDERAL_HOLIDAYS_2026,
    TIMEZONE,
    WINDOW,
    WORKPLACE_ID,
    HartwellGenesis,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workplaces.hartwell.voice import VOICE

__all__ = [
    "EPOCH_ISO",
    "FEDERAL_HOLIDAYS_2026",
    "TIMEZONE",
    "VOICE",
    "WINDOW",
    "WORKPLACE_ID",
    "HartwellGenesis",
    "build_genesis",
    "day_profile",
    "procedural_cast",
]

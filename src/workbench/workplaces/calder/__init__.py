"""Calder & Finch, CPAs: a medium-size accounting firm over six months.

Sixteen people at genesis, a staff accountant who joins in March, ten
clients, and a full accounting calendar: January year-end closes, filing
season, the April 15 crunch, quarterly estimates, and a nonprofit audit.
``build_genesis`` produces the time-zero event sequence; ``procedural_cast``
derives the background-traffic cast (growing once the arrival lands) and
``day_profile`` the shape of each calendar day. ``VOICE`` carries the
firm's register.
"""

from workbench.workplaces.calder.genesis import (
    EPOCH_ISO,
    FEDERAL_HOLIDAYS_2026,
    LIVE_DAY,
    LIVE_DAY_INDEX,
    LIVE_DAY_OFFSET,
    TIMEKEEPER_RATES,
    TIMEZONE,
    WINDOW,
    WORKPLACE_ID,
    CalderGenesis,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workbench.workplaces.calder.people import ARRIVAL, ARRIVAL_DATE
from workbench.workplaces.calder.voice import VOICE

__all__ = [
    "ARRIVAL",
    "ARRIVAL_DATE",
    "EPOCH_ISO",
    "FEDERAL_HOLIDAYS_2026",
    "LIVE_DAY",
    "LIVE_DAY_INDEX",
    "LIVE_DAY_OFFSET",
    "TIMEKEEPER_RATES",
    "TIMEZONE",
    "VOICE",
    "WINDOW",
    "WORKPLACE_ID",
    "CalderGenesis",
    "build_genesis",
    "day_profile",
    "procedural_cast",
]

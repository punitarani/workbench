"""Simulation-layer error taxonomy, rooted in the core WorkbenchError."""

from core.errors import WorkbenchError


class SimulationError(WorkbenchError):
    """Root of engine and runtime errors."""


class LMError(SimulationError):
    """Base for language-model layer failures."""


class LMTransportError(LMError):
    """The provider could not be reached or returned a non-success status."""


class LMResponseError(LMError):
    """The provider responded, but the body was not usable."""


class CassetteMissError(LMError):
    """Replay required a recording that does not exist. Never silent."""


class LMBudgetExceededError(LMError):
    """The configured call or token budget was exhausted. Never silent."""


class PhaseError(SimulationError):
    """An entity attempted an illegal component-lifecycle transition."""


class SnapshotError(SimulationError):
    """A snapshot could not be taken or restored exactly. Nothing is dropped."""


class TimeError(SimulationError):
    """Simulated time attempted to move backward."""


class ConfigMismatchError(SimulationError):
    """A snapshot was taken under a different configuration than the resume."""


class TransportError(SimulationError):
    """An externalized entity's transport failed."""


class ScriptExhaustedError(TransportError):
    """A scripted transport ran out of recorded responses. Never silent."""


class SeatProtocolError(TransportError):
    """An interactive seat was driven out of order (act before turn, double
    submit, or a submit after the day ended)."""


class ConfigError(SimulationError):
    """A workplace or scenario configuration is invalid. Names the offender."""


class ChronicleError(SimulationError):
    """A chronicle was assembled out of order or outside its calendar window."""

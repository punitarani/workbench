"""Simulation-layer error taxonomy, rooted in the core WorkbenchError."""

from workbench.core.errors import WorkbenchError


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

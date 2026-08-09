"""Core error taxonomy. Simulation-layer errors extend WorkbenchError there."""


class WorkbenchError(Exception):
    """Root of every Workbench-raised error."""


class SchemaError(WorkbenchError):
    """A model or payload failed schema-level validation."""


class WorldLogError(WorkbenchError):
    """Base for world-log read/write failures."""


class WorldLogOrderingError(WorldLogError):
    """An append would violate seq/time ordering invariants."""


class WorldLogIntegrityError(WorldLogError):
    """A stored log failed validation on read."""

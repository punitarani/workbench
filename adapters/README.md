# adapters

Bridges from the Workbench environment to non-Harbor frameworks (Prime,
Tinker, …). Deliberately deferred: no package exists until there is a
concrete second consumer, because a compatibility layer designed against
imagined requirements is worse than none. The engine's `ActTransport`
protocol (`simulation/src/workbench/simulation/external/`) is the seam an
adapter will plug into.

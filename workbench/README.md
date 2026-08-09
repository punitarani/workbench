# workbench (core)

The shared contracts every other layer builds on — and, in later phases, the
agent-facing environment itself (container runtime, tool servers).

Today this package is `workbench.core`: the typed vocabulary of professional
work. Events (email, chat, documents, tickets, calendar, people), the intents
that produce them, action specs, deterministic ids and seeds, and the world
log — an append-only JSONL stream with a validator that proves every
reference resolves.

Nothing here knows about legal work, simulation, or language models. If a
concept only makes sense for one domain or one layer, it does not belong in
core.

Also here, under `environment/`: the `Dockerfile` and `run-as-environment.c`
setuid shim — the container image for the Phase 2+ agent environment.

Start with [`docs/simulation-engine.md`](../docs/simulation-engine.md) for
how these contracts are used.

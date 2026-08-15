# ADR-0005 — Gmail write surface is draft-only

Status: accepted · Date: 2026-08-14

## Context

Google's official Gmail MCP server (Developer Preview, August 2026)
exposes ~18 tools — search, read, labels, drafts, trash, spam — and
**deliberately has no send tool**. A human opens the draft and sends it.

Our agent-facing Gmail surface is currently read-only. Simulation
personas "send" mail through engine intents, which are a different
mechanism entirely (grounded by the GM, not exposed as tools).

## Decision

The Gmail write surface implements **`create_draft` and `list_drafts`,
label tools, and trash/spam tools — and no send tool**, matching the
official server exactly. Agent-authored mail that must "go out" in a
task is expressed as a draft plus, where a task needs delivery, an
explicit non-Gmail action the grader reads.

## Consequences

- Parity is exact on the dimension an MCP engineer would check first.
- The safety posture matches the official product's: an agent cannot
  send mail on anyone's behalf through this surface, so no task can
  train that behavior by accident.
- Write-workflow tasks on Gmail grade on **draft state, labels, and
  triage decisions**, which is a fine and realistic target (inbox
  triage is genuine professional work).
- If a future task genuinely needs send semantics, it must be argued in
  a new ADR and would be a deliberate, documented divergence from the
  official surface — not a quiet addition.

# ADR-0003 — Documented volume scale factor

Status: accepted · Date: 2026-08-14

## Context

A real 17-professional CPA firm generates on the order of 300–500 emails
a day firm-wide, hundreds of concurrent engagements, and thousands of
documents a year. v1 produced 21.8 emails/day, 21 matters, 8 documents.

Full 1:1 volume would require roughly 10× v1's LM budget (v1: 29.6k
calls, 20.6h, ~$30 for 140 workdays) — on the order of 300k+ calls and
several days of wall clock per epoch, before any tuning iterations. That
cost buys *repetition*, not new structure: the tenth close of the month
teaches a model little the third did not.

The three hostile inspections weigh differently here. A statistician
inspects **shape** — distributions, tails, correlations — which is
scale-invariant. An MCP engineer inspects signatures, also
scale-invariant. Only the CPA partner reads absolute volume.

## Decision

Target **~3–5× v1 volume**, not 1:1 with a real firm. The scale factor
is uniform across surfaces, so all *ratios* (emails per matter, hours
per engagement, documents per close, attachments per deliverable) stay
realistic. The factor is **stated explicitly** in `FIDELITY-REPORT.md`
so no reader mistakes the world for a real firm's raw volume.

## Consequences

- Distribution bands (PLAN §5) are written at the scaled level; the
  shape assertions (KS, Gini, tails, correlation) are the real gate.
- The CPA-partner audit rubric (P8) judges *ratios and artifacts*, with
  absolute volume explicitly out of scope and the scale factor disclosed
  to the reviewer persona.
- If a future epoch wants 1:1 volume, the generators do not change —
  only the scale constant and the budget.
- Honesty requirement: any external presentation of this dataset must
  carry the scale factor. Silent omission would misrepresent the world.

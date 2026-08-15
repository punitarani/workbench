# ADR-0007 — Billing, tax, and ledger ship as separate tool systems

Status: accepted · Date: 2026-08-14

## Context

v2 adds the CPA-defining surfaces v1 lacked: time & billing (WIP,
invoices, AR, realization), tax workflow (returns, extensions, e-file
acknowledgments, notices), and client ledger/payroll. These could either
extend the practice-management system or ship as their own
`ToolSystem`s.

The framework makes the choice cheap either way: a system is a name,
handled tags, tables, a projector, and a registrar, plus one registry
line — with structural enforcement that offstage `sim.*` events can
never reach a tool database.

Real firms run these as **separate products** with separate logins: a
practice-management system, a tax-prep package, a GL/payroll platform.
Agents in the real job move between them, and the seams between systems
are part of the work (a number in the tax package has to agree with the
ledger).

## Decision

Ship `billing`, `tax`, and `ledger` as **separate tool systems**, each
with its own database, MCP server, and id space.

## Consequences

- The environment mirrors the real desktop: cross-system reconciliation
  becomes a *task class* rather than an artifact of one schema.
- Each system's referential integrity is checkable independently, and
  cross-system agreement becomes an explicit coherence check (the
  invariant that a filed return's numbers match the ledger's).
- More MCP servers per bundle: more processes and a larger `mcp.json`.
  Acceptable — the container already runs five.
- Tasks can scope tightly (one system) or deliberately span systems for
  harder work.
- Cost: three new projectors and three new server surfaces to keep in
  parity discipline. Since no official MCP servers exist for tax-prep or
  GL products in this class, these are *modeled* surfaces (like
  practice management post-ADR-0001) and the matrix records them as
  such, with their API lineage named.

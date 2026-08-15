# ADR-0001 — Practice-management product identity

Status: accepted (default per the v2 directive) · Date: 2026-08-14

## Context

Our practice-management surface is named and shaped after **Clio**, a
*legal* practice-management product, while the world it serves is a CPA
firm. Two facts from the August 2026 parity sweep:

- **No official Clio MCP server exists.** Clio's developer docs contain
  no MCP mention; registries list only community servers. The de-facto
  standard is the community `@oktopeak/clio-mcp` (26 tools, listed on
  Anthropic's MCP registry).
- Clio's v4 REST grammar — `{data: ...}` envelopes, etags, matters,
  activities with a `type` discriminator, `display_number`, cursor
  pagination — transfers cleanly to accounting practice management
  (Karbon, Canopy, CCH). The *semantics* are right; the *skin* is wrong.

A CPA partner reading the environment sees a legal product; an MCP
engineer diffing signatures has no official server to diff against.

## Decision

**Keep the API grammar, reskin the product identity accounting-native.**
The tool system is renamed to an accounting-native practice-management
product; tool names, parameter shapes, envelopes, and pagination stay
compatible with the community Clio surface (the closest thing to a
standard), with legal terms of art replaced by accounting ones in
descriptions and vocabulary (matter → engagement in prose; the wire
field names stay stable where they carry the grammar).

## Consequences

- The vocabulary lint (workstream E3) becomes enforceable: legal terms
  of art in an accounting practice are a test failure.
- We lose "diff against Clio community server" as a parity claim for
  this one surface; the parity matrix records it as a *modeled* surface
  with a named lineage rather than an emulated official one.
- Renaming touches the tool system name, database filename, `mcp.json`
  spec, and task bundles — all cassette-safe (environment-side).
- If Clio ever ships an official MCP server, the grammar compatibility
  means parity work would be additive, not a rewrite.

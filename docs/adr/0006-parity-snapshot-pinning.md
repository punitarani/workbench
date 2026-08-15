# ADR-0006 — Parity is pinned to dated snapshots

Status: accepted · Date: 2026-08-14

## Context

Parity has to be *checkable in CI*, but the official surfaces are moving
targets and two of them publish no schemas at all:

- **Slack** (GA February 2026) grew from 13 to 19 tools during 2026 and
  states that `tools/list` is the source of truth; published tool
  signatures come from third-party gateway captures.
- **iManage** (GA ~May 2026) publishes tool *descriptions*, not JSON
  schemas — only `container_id` and `query` are verbatim-confirmed
  parameter names.
- **Google** publishes real references, but its live Gmail server serves
  8 trash/spam tools whose doc pages 404 — the docs lag the deployment.
- **Clio** has no official server at all (see ADR-0001).

A CI test asserting "we match the official server" against an
unversioned remote would be both flaky and untrue.

## Decision

Pin **dated `tools/list` snapshots** per vendor under
`tests/parity/snapshots/<vendor>-<YYYY-MM-DD>.json`, each recording its
provenance (published reference, live capture, or third-party capture)
and confidence. CI asserts our surface against the snapshot, and
`PARITY-MATRIX.md` lists every official tool as *implemented* or
*waived with a reason*. Refreshing a snapshot is a deliberate, reviewed
commit that updates the matrix in the same change.

## Consequences

- Parity claims become precise and falsifiable: "matches the Slack
  surface as captured 2026-08-14", not "matches Slack".
- Vendor drift surfaces as a reviewed diff, not a silent divergence or
  a red CI on someone else's release schedule.
- Signature confidence is recorded honestly per field, so anyone
  training on this data knows which parameter names are verbatim-
  confirmed and which are inferred.
- A refresh procedure must live next to the snapshots, including how to
  capture from an authenticated live server where that is the only
  truth available.

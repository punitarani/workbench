# Parity matrix — emulated surfaces against the official MCP servers

Living document, CI-checked by `tests/parity/`. Every official tool is
**implemented** or **waived with a reason**; every waiver is a line in the
vendor's snapshot file, not a silence. Parity is pinned to dated captures
under `tests/parity/snapshots/` (see the design decisions in
[`WORKBENCH.md`](../../WORKBENCH.md)) because the official surfaces
move — Slack grew from 13 tools to 19 during 2026, Google's live Gmail
server serves eight tools whose documentation pages 404, and iManage
publishes descriptions rather than JSON schemas.

## Status by vendor

| Vendor | Official | Implemented | Waived | Snapshot | Confidence |
|---|---|---|---|---|---|
| gmail | 19 | 19 | 0 | 2026-08-14 | high (published reference + live capture) |
| calendar | 9 | 9 | 6 params | 2026-08-14 | high (published reference) |
| slack | 19 | see snapshot | see snapshot | 2026-08-14 | medium (third-party gateway captures) |
| imanage | 15 | see snapshot | see snapshot | 2026-08-14 | medium (descriptions published, schemas not) |
| practice management | n/a | modeled surface | — | — | no official server exists |
| billing / tax / ledger | n/a | planned, unbuilt | — | — | no official servers in this class |

## gmail — complete

All 19 tools: `search_threads`, `get_thread`, `get_message`,
`list_drafts`, `create_draft`, `list_labels`, `create_label`,
`label_message`, `unlabel_message`, `label_thread`, `unlabel_thread`,
`trash_message`, `untrash_message`, `trash_thread`, `untrash_thread`,
`mark_message_spam`, `unmark_message_spam`, `mark_thread_spam`,
`unmark_thread_spam`.

Deliberate boundary: **no send tool**, matching the official server.
`apply_sensitive_message_label` / `apply_sensitive_thread_label`
appear in doc cross-links but are not served by the live server, so they
are not emulated.

Response shape: Message carries `htmlBody` (derived from the stored
plaintext) and the official key order. `messageFormat` and `view` enums
are verbatim.

## calendar — complete

All 9 tools: `list_events`, `get_event`, `list_calendars`,
`search_events`, `suggest_time`, `create_event`, `update_event`,
`delete_event`, `respond_to_event`.

Drift fixed: `orderBy` takes the official vocabulary
(`default|startTime|startTimeDesc|lastModified`); `timeZone` and
`eventType[]` added; the response carries `timeZone` and `accessRole`;
the Event carries `recurrence` and `availability`.

Waived parameters (six, each recorded in the snapshot with a reason):
conferencing (`addGoogleMeetUrl`, `googleMeetUrl`), reminder delivery
(`overrideReminders`, `defaultReminders`), cosmetics (`colorId`), and
calendar-side attachments — this world models attachments on the
document surface, and conferencing and reminder delivery are not
modeled at all.

## slack, imanage

See the vendor snapshots for the implemented/waived split; CI asserts it.
Both vendors declare live `tools/list` the only source of truth, so the
snapshots record capture date and confidence rather than claiming an
absolute match.

## Modeled surfaces (no official server to match)

Practice management has no official MCP server in its product class. It
is a *modeled* surface: its API grammar follows a named lineage (the
community Clio surface and Clio v4 REST), and the matrix records it as
modeled rather than emulated so nobody mistakes an in-house design for
vendor parity. The compliance write surface is likewise in-house by
design. Billing, tax, and ledger are planned as further modeled systems
and do not exist yet.

## Refresh procedure

1. Capture the vendor's current `tools/list` (authenticated where that is
   the only truth available).
2. Write a new dated snapshot in `tests/parity/snapshots/`, filling in
   `captured`, `provenance`, and `confidence` honestly.
3. Run `uv run pytest tests/parity -q`; every new or changed tool either
   gets implemented or gets a waiver line with a reason.
4. Update this matrix in the same commit, so review sees the diff.

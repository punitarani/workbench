# MCP tool-surface parity & document generation — audit and plan

Companion to REALISM-REVIEW.md. Two questions: (1) do our five emulated
MCP servers match the official servers tool-for-tool and
signature-for-signature (training-critical), and (2) does the document
pipeline produce enough high-fidelity office files. Method: AST-level
signature extraction from our servers, against official tool
enumerations gathered August 2026 (Google's published MCP references +
live tools/list; Slack's GA server via gateway captures; iManage's
published connector docs; Clio registry sweep).

## Part 1 — MCP parity, server by server

Headline: **our tool names and casing are almost perfectly aligned on
the read surfaces — every one of our 25 emulated business tools exists
in its official counterpart with the same name.** The gaps are (a) the
official servers' newer read tools, (b) parameter enrichments
(`response_format`, `view`/`messageFormat` enums, filters), and above
all (c) **write tools: the official servers grew substantial write
surfaces in 2026 and we emulate none of them** (except the bespoke
compliance server, which proves the write-aperture pattern works).

### gmail — ours 4 tools, official ~18 (10 documented + 8 live)

| Ours | Official match | Signature drift |
|---|---|---|
| `search_threads(query, pageSize=20, pageToken)` | ✓ same name/casing | missing `includeTrash: bool`, `view: ThreadView` enum; official caps pageSize at 50 |
| `get_thread(threadId)` | ✓ | missing `messageFormat` enum (MINIMAL / FULL_CONTENT / METADATA_ONLY) |
| `get_message(messageId)` | ✓ | missing `messageFormat` |
| `list_labels()` | ✓ | missing `pageSize`, `pageToken` |

Missing tools (14): `list_drafts`, `create_draft`, `create_label`,
`label_message`, `unlabel_message`, `label_thread`, `unlabel_thread`,
plus live-server `trash_message`/`untrash_message`/`trash_thread`/
`untrash_thread`/`mark_message_spam`/`unmark_message_spam`/
`mark_thread_spam`/`unmark_thread_spam`.

Return-shape drift: official Message adds `htmlBody`, attachment
metadata objects (`id`, `mimeType`, `filename`), and
`resultCountEstimate` on search; ours has no `htmlBody`.

Strategic note: **the official server cannot send** — drafts only, a
human hits send. Our sim personas "send" through engine verbs, not the
tool, so full parity is achievable without granting agents real send.

### calendar — ours 3 tools, official 9

| Ours | Official match | Signature drift |
|---|---|---|
| `list_events(calendarId, startTime, endTime, fullText, orderBy, pageSize, pageToken)` | ✓ (and official confirms `startTime`/`endTime`, not REST `timeMin`) | `orderBy`: ours `"updated"` vs official `"lastModified"` (+ `"default"`, `"startTimeDesc"`); missing `timeZone`, `eventType[]` |
| `get_event(eventId, calendarId=None)` | ✓ exact | — |
| `list_calendars(pageSize=100, pageToken)` | ✓ exact | — |

Missing tools (6): `search_events`, `suggest_time`, `create_event`,
`update_event` (delta-style `addedAttendees`/`removedAttendeeEmails`),
`delete_event`, `respond_to_event` — the RSVP tool whose absence
explains our world's 262 permanently-`needsAction` attendees.

Return-shape drift: official Event is far richer — `recurrence[]`
(RFC 5545), `eventType`, `availability`, `conferenceUrl`,
`guestPermissions`, `attendees[].responseStatus`.

### slack — ours 9 tools, official 19 (GA Feb 2026, mcp.slack.com)

All 9 of ours exist officially under identical names:
`slack_search_channels`, `slack_read_channel`, `slack_read_thread`,
`slack_search_public`, `slack_search_public_and_private`,
`slack_search_users`, `slack_read_user_profile`,
`slack_list_channel_members`, `slack_get_reactions`. Drift: official
adds `response_format: "detailed"|"concise"|"ids_only"` on most tools;
searches add `content_types`, `after`/`before`, `context_channel_id`,
`include_bots`, `include_context`, `max_context_length`,
`sort`/`sort_dir`; `slack_read_user_profile.user_id` is optional
(defaults to caller — ours requires it); members adds `include_bots`,
`include_deleted`; channels adds `include_archived`, `channel_types`.

Missing tools (10): reads `slack_search_emojis`, `slack_read_file`,
`slack_read_canvas`; writes `slack_send_message`,
`slack_send_message_draft`, `slack_schedule_message`,
`slack_create_conversation`, `slack_add_reaction`,
`slack_create_canvas`, `slack_update_canvas`.

Format note: the official server returns rendered text blocks, not raw
API JSON; ours returns dicts. Slack explicitly says `tools/list` is the
source of truth and surfaces change — parity needs a pinned snapshot.

### imanage — ours 9 tools, official Work connector 15 (GA ~May 2026)

All 9 of ours exist officially: `search`, `search_workspaces`,
`get_workspace_profile`, `get_container_children` (param
`container_id` verbatim-confirmed), `get_document_profile`,
`get_document_versions`, `download_document`, `get_libraries`,
`get_user_information` (param `query` verbatim-confirmed; empty string
= current user — ours matches).

Missing tools (6): `fetch`, `get_rows_from_csv_document`,
`get_recent_documents`, `get_recent_workspaces`,
`get_workspace_templates`, `list_actions`.

Two fidelity caveats: (1) iManage publishes descriptions, not JSON
schemas — byte-exact parity requires an authenticated `tools/list`
against `cloudimanage.com/mcp/work`; (2) ~~official document ids use the
`LIBRARY!number.version` grammar (`ACTIVE!5482.3`) — ours uses
`doc-000001`, a visible tell.~~ **Correction (2026-08-14):** this audit
claim was wrong. The server already minted the official grammar at its
boundary (`LEGAL!1.2`); `doc-000001` is the *stored* id, which the world
log needs for coherence and which never reaches a caller. v2 centralized
that translation in one helper and added round-trip tests. Official pagination: 100/page, 500 max,
100 calls/60s throttle.

### clio — ours 8 tools; **no official server exists (confirmed Aug 2026)**

Clio's developer docs contain no MCP mention; registries list only
community servers. Our docstring is accurate. The de-facto standard is
the community `@oktopeak/clio-mcp` (on Anthropic's MCP registry, 26
tools) — notable because it is write-heavy: `create_matter`,
`log_time_entry`, `create_activity`, `create_note`, `create_task`/
`update_task`/`complete_task`, `create_calendar_entry`,
`get_billing_summary`, `upload_document`. Our read shapes (v4-style
`{data: ...}` envelope, etags, display numbers) match Clio's REST
conventions; missing vs v4: `/bills` (invoices), `/tasks`,
`/communications`, `/documents`, `page_token` pagination and `fields=`
sparse fieldsets.

Given the realism review's finding that Clio is a *legal* product skin
on an accounting firm, the choice is: (a) full parity with the Oktopeak
surface as the de-facto Clio standard, or (b) reskin to an
accounting-native practice tool where no official MCP constrains us.
Either way the missing *capabilities* (billing, tasks, write tools) are
the same work.

## Part 2 — document generation: fidelity, quantity, implementation

### What exists (and is well-engineered)
- Typed content models: `SpreadsheetContent` (sheets/columns/rows) and
  `FormattedDocument` (heading/paragraph/list/table blocks), stored as
  canonical JSON in the world log — determinism over JSON, rendered
  bytes derived. This is the right architecture.
- Real renderers at materialization: xlsx via openpyxl, docx via
  python-docx, PDF via LibreOffice when present; parse failures fall
  back to `.txt` **with the skip recorded** — never silent.
- Email attachments are fully grounded (`attach_document_refs`
  validated against real documents at grounding).

### What the epoch actually produced (the indictment)
- **8 documents in 140 days — every one a compile-time seed.** Zero
  runtime document creations by any persona in six months.
- 8 revisions, one of which wrote prose into a `formatted` document
  (renders as `.txt` fallback) — format is not validated at grounding.
- **0 attachments on 3,048 emails** despite the grounded affordance;
  drafts *say* "attached is the signed copy" and attach nothing.
- File-type census of the agent workspace: 5 `.md`, 2 `.xlsx`, 1 `.txt`
  (failed docx). No client folder ever created.

### Fidelity ceiling (implementation gaps)
1. **Creation is markdown-hardcoded**: `_ground_document`'s create path
   sets `content_format="markdown"` unconditionally, and
   `DocumentCreateSpec` has no format field — personas *cannot* create
   a spreadsheet or Word document even if prompted to.
2. **No PowerPoint anywhere**: no slide-deck content model, no
   python-pptx renderer.
3. **No spreadsheet formulas**: cells are literals only — for an
   accounting world, formula-bearing workbooks are the core artifact.
4. **Formatted blocks are minimal**: no images, no headers/footers, no
   page breaks, no styling/merges/column widths.
5. **No grounding-time format validation**: malformed structured
   content is stored and only surfaces at render time.

### Upgrade plan (ordered)
1. **Format-aware creation** — `DocumentCreateSpec.content_format`
   (markdown | formatted | spreadsheet | slides) + GM parse-validation
   with instructive rejection (same loop that fixed refs and threads).
2. **Slide model + renderer** — `SlideDeck` (title/bullets/table/notes
   per slide) → python-pptx; add `slides` to the render dispatch with
   the same `.txt` fallback contract.
3. **Spreadsheet formulas** — a `{"formula": "=SUM(B2:B13)"}` cell
   variant; openpyxl writes formulas natively; canonical JSON stays
   deterministic.
4. **Deliverable pressure** — decide/draft guidance + seed playbooks
   that route work products into documents (close packages, K-1
   cover letters, financial summaries as spreadsheets) and attach them
   to the mail that announces them; per-client folders
   (`/clients/{name}/...`) in the path grammar.
5. **Volume mechanics** — pair with the realism review's timesheet
   batching: every close, filing, and delivery mints its document, so
   an epoch produces hundreds of typed office files, not eight.

## Part 3 — implementation plan and blast radius

**Safe now (no sim-cassette impact — the tool servers are
environment-side only):**
- All Part 1 read-tool signature alignments (params, enums, defaults,
  return fields) and new read tools over existing projections
  (drafts/recent/templates/csv-rows/search_events/suggest_time...).
- Write tools with the compliance-server pattern: agent-visible action
  tables in the projected DBs (draft created, label applied, message
  posted, event created/responded, time logged), graded on resulting
  state. This unlocks outcome-graded *write* tasks on every surface —
  the single highest-value training upgrade.
- iManage id-grammar (`LIBRARY!number.version`) and Slack rendered-text
  response option (`response_format`).
- A parity regression suite: pinned `tools/list` snapshots per official
  server, asserted against ours in CI, refreshed deliberately.

**Next epoch revision (invalidates acceptance cassettes — batch
together):** document-creation format field + grounding validation,
attachment/deliverable prompt pressure, slide/formula models, plus the
realism review's items (timesheets, lifecycle verbs, busy-season
cohorts).

**Judgment calls for the user:**
- Clio: parity-with-community-standard vs accounting-native reskin.
- Gmail sending: official has no send tool — keep agent sends
  draft-only (matches official; safer) or diverge deliberately.
- Slack/iManage byte-exactness: both vendors treat live `tools/list`
  as truth; pinning a dated snapshot in the parity suite is the honest
  contract.

## Sources

Google: developers.google.com Gmail MCP reference (tools_list pages),
Calendar MCP reference (api/v3/reference/mcp), Workspace MCP
configuration guide, plus live Gmail tools/list schemas.
Slack: docs.slack.dev/ai/slack-mcp-server, slack.com MCP help +
real-time search announcement, scalekit.com/connectors/slackmcp
(19-tool capture), docs.dust.tt/docs/slack-mcp, portkey.ai and
mintmcp.com earlier snapshots.
iManage: learn.microsoft.com/connectors/imanageworkmcp (15-tool list),
docs.imanage.com MCP server help (verbatim descriptions), imanage.com
GA announcement, promptarmor.com independent confirmation.
Clio: docs.developers.clio.com (no MCP), github.com/oktopeak/clio-mcp
(+ Anthropic MCP registry listing), github.com/lawyered0/clio-mcp,
pulsemcp.com registry.

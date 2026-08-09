# Decisions — four-month history run

Assumptions and judgment calls made while executing autonomously; each
entry says what was ambiguous and which reading was taken.

1. **Prior GEPA spend counts against the cap.** The goal's cap names GEPA;
   tonight's persona-optimization spend (~$0.23 est) predates the goal but
   is the same key and purpose, so it is in the ledger.
2. **Deliverable docs live under `docs/runs/2026-08-09-four-month-history/`**
   — the repo rule routes documentation to `docs/`; DECISIONS.md and
   LEDGER.md are documentation of this run.
3. **GEPA verdict: infrastructure and one structural fix shipped;
   instruction adoption deferred to the Phase 2 pilot.** The loop found
   and fixed a real grounding bug (personas could not see their chat
   channels — committed), and proved the shipped `decide` text never
   initiates chat (0.525 on 4/4 seeds). But no *generic* candidate passed
   both gates: the scenario winner (0.938 train / 0.900 delivery-metric
   holdout) produced a degenerate full day (3 emails, zero document
   revisions — narration-as-work); the delivery-aware rerun's winner
   quoted the evaluation day verbatim (reward hacking, mechanically
   banned thereafter); generic-forced mutations scored 0.300-0.600.
   Hand-merges failed twice (0.525, 0.400) — instruction efficacy is
   phrasing-order sensitive, so only measured text ships. The original
   instruction is restored; the goal's own structure (new 12-person firm,
   new tool schemas, pilot-then-GEPA) makes further tuning against the
   6-person org wasted spend. Evidence: out/gepa-run{1..4}, holdouts.
4. **Deferred wake-time semantics**: recorded days keep intra-day
   scheduling; the chronicle will offset compiled times per day and
   thread minter state by scanning the log (no engine changes).
5. **Budget cap counts OpenRouter model spend** (GEPA, generation, evals),
   not the orchestrating assistant's own tokens.
6. **Phase 1 product mapping** (research: four agent reports, 08-09):
   - mail → **Gmail**: Google's official Gmail MCP (May 2026 preview).
     Mirror `search_threads`/`get_thread`/`get_message`/`list_labels`
     with the flattened Message shape (id, snippet, subject, sender,
     toRecipients, ccRecipients, date ISO-8601, plaintextBody,
     attachments[{id,mimeType,filename}], labelIds). pageToken paging,
     documented `query` operator subset. `list_labels` returns user
     labels only → empty list is spec-legal v1; system labels derived.
   - chat → **Slack**: official hosted MCP tool names
     (`slack_read_channel`, `slack_read_thread`, `slack_search_public`,
     `slack_search_channels`, `slack_search_users`,
     `slack_read_user_profile`, `slack_list_channel_members`,
     `slack_get_reactions`) with Web-API-shaped JSON responses (the
     official server returns markdown; JSON field names follow the
     archived reference/Web API: ts "sec.micro" identity, thread_ts,
     reactions [{name,users,count}], topic/purpose {value}).
   - dms → **iManage**: OFFICIAL iManage MCP exists (GA 2026-05-14).
     Mirror `search`, `search_workspaces`, `get_workspace_profile`,
     `get_container_children`, `get_document_profile`,
     `get_document_versions`, `download_document`, `get_libraries`,
     `get_user_information`. Ids `{library}!{number}.{version}`;
     workspaces are matters; custom1=client, custom2=matter;
     class/subclass; versions carry full profiles.
   - matters → **Clio** (no official MCP exists in the category —
     decided on API documentation quality + market leadership). MCP-shaped
     read tools over Clio v4 resources: matters (number +
     display_number "00001-Client", Pending/Open/Closed with per-status
     dates), matter contacts/relationships, activities (time entries,
     quantity in seconds), notes, users, who_am_i, contacts; {data}
     envelope, integer ids.
   - **No generic `directory` tool** on these servers (realism): people
     surfaces are Slack user tools, iManage get_user_information, Clio
     users/contacts. The shared people table stays in every db as the
     projection source.
   - **Mailbox scoping**: Gmail serves one seat's mailbox
     (`--user` on serve; `materialize(..., seat=...)`); INBOX/SENT/
     UNREAD derived per seat. Org-global reading moves to the systems
     that are genuinely org-global (iManage, Clio, Slack publics).
7. **Core payload extensions (additive, optional)**: `chat.reaction.added`,
   conversation `topic`/`purpose`, `work.time.logged` (Clio activity
   substrate), `org.record` (client/vendor/court companies) +
   `person.record.organization`, `ticket.created.client_ref`. Everything
   else (snippets, labels, display numbers, ts ids, document numbers,
   workspace trees) derives at projection. Golden logs regenerate
   deliberately if serialization shifts.
8. **Pilot verdict (284 events, coherence-clean, byte-reproducible)**:
   structure good; two realism gaps for the full build — chat routed
   only to #general, and all documents in one workspace. Both are
   generator routing fixes, not persona problems. **GEPA skipped for
   Phase 2**: the pilot exercises no persona programs, and recorded-day
   persona quality was already proven by the 12/12 acceptance suite on
   the re-recorded legal day; the GEPA verdict in entry 3 stands.
9. **Tier A realized as directed days, not engine GABM days**: storyline
   beats are deterministic scripts; an LM authors bodies/redline diffs
   (cached to a content store keyed by prompt hash, so the full history
   reproduces from seed + committed-out cache... cache is data, stays
   gitignored; reproduction needs the key or the cache). Rationale: the
   engine's 8-attempt fragility history at 6 personas, a 12-person org
   multiplies that risk; tasks depend on record content, not emergent
   behavior; engine days remain the path for interactive variants.

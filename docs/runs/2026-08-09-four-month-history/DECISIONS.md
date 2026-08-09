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
10. **Load-bearing storyline facts are code constants, not LM output.**
   Documents assemble LM prose around verbatim clause constants (the
   playbook's three-year standard, the NDA term/residuals clauses, the
   Lumen indemnity paragraph), so evidence properties — v3 drops exactly
   the indemnity paragraph, the NDA practice diverges from the playbook —
   hold by construction rather than by hoping a small model reproduces a
   paragraph verbatim. The LM authors what realism needs (recitals,
   emails, long notes); code owns what the tasks will grade.
11. **S4 closure feeds back into procedural traffic**: from the day after
   the Cascadia matter closes, the procedural cast drops that matter, so
   no background time entries or comments land on a closed file. The
   swap keys off `S4_CLOSED_DATE` in the build script.
12. **The epoch is projected data, not a server constant.** All four MCP
   servers hardcoded the legal demo's epoch (2026-03-12), so every date
   they served on hartwell workspaces (epoch 2026-03-02T00:00:00-08:00)
   was +10 days off grader truth — the cause of the universal 0.75
   vanished-clause plateau (Luna's round-2 diff was perfect except the
   shifted date). Fix: `project_system` writes a shared `meta` table and
   servers derive dates via `framework.read_epoch` at call time. Only
   the epoch string leaves `sim.run.started`; run_id, seed_root,
   config_hash, and schema_version stay offstage
   (`test_meta_carries_only_the_epoch` locks the contract). Rendering
   follows each product: iManage converts to true UTC `Z` timestamps,
   Gmail serves the epoch's own offset, Clio and Slack use local
   calendar dates; the four system tests' fixture assertions moved
   accordingly.
13. **Round-3 hardening.** (a) *operative-deadline*: genesis declares 10
   standing DM pairs and procedural days weave template DM traffic
   (Grace<->Samuel at 0.8 exchanges/workday); the S5 correction now
   posts mid-stream into that 157-message thread (position ~130), and
   the audit gates >=8 DMs plus a mid-stream correction. Conversation
   enumeration no longer finds it: the post-fix Luna probe scored
   0.3666, reporting the stale June 18 after exhausting public-channel
   keyword search without opening a DM, while solve.sh still earns 1.0.
   (b) *vanished-clause*: the instruction stopped naming the Lumen
   agreement (Eleanor certifying "no protection was negotiated away this
   quarter"); five genesis firm documents gained additive multi-version
   histories (corpus: 12 multi-version documents, 7 with 3+ versions,
   +5 content calls), and solve.sh became a corpus-wide
   consecutive-version diff with gates (>=10 multi-version docs, >=5
   deep, exactly one silent drop). (c) *standard-drift*: the brief said
   to move "whichever component the probe earned last" behind the
   oblique pattern; the post-epoch-fix probe (Luna 0.675) showed the
   model earning every substantive component from the version diff
   itself — its losses were path formatting and a phrasing marker, not
   discoverability — so the hardening went to the one component still
   earnable by pure keyword search: the accepted term length, which
   four emails stated as "five-year". Those emails were re-authored
   oblique (no term lengths anywhere in mail or chat, audited), so the
   term practice now requires the v1/v2 diff exactly like the residuals
   clause. Grader values unchanged on every task; fee-dispute and
   client-departure untouched except `_evidence` id refreshes after the
   rebuild shifted minted ids (no graded field there references ids).

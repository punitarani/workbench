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
14. **Round-4 diagnosis and hardening.** Diagnosis (6 probe episodes with
   kept transcripts + round-3 transcripts regraded per part offline):
   (a) *DEFECT — iManage paths were unobservable.* No iManage tool
   response ever carried the `path` column (search hits, profiles,
   container children all omit it), yet standard-drift grades three path
   fields (0.25 total), vanished-clause one (0.10), client-departure one
   (0.15). Every model on every round-3 attempt substituted
   `workspace/Title` approximations or the `LEGAL!n.v` display id — the
   uniform 0.75/0.90/0.85 plateaus are exactly those weights, verified
   by per-part regrades (GLM standard-drift probe missed precisely
   playbook_path + both document paths, nothing else; DeepSeek
   client-departure missed precisely the letter path). Fix like the
   epoch bug: profiles, search hits, and container children now serve
   `path`; system tests updated.
   (b) *DEFECT — the eval harness corrupted structured deliverables.*
   `write_file` coerced non-string `content` with `str()`, so a model
   passing a JSON object wrote Python-repr pseudo-JSON that every
   grader's `json.loads` rejects. GLM emits object content
   intermittently (2 of 5 round-4 probes; its fee-dispute answer was
   substantively perfect and scored 0.0000). Explains round-3's stray
   GLM 0.0s. Fix in the adapter only: dict/list content is
   `json.dumps`-ed; graders untouched; regression test added.
   (c) *operative-deadline split.* DeepSeek/Luna find the DM by
   enumeration — `slack_search_channels("")`, member-listing all 10
   DMs, then reading the Grace/Samuel pair — not via any search leak.
   GLM spends all 30 turns on `slack_search_public` (which excludes DMs
   by construction) and never writes a deliverable: its three 0.0s are
   honest turn exhaustion, not a defect. A round-4 DeepSeek probe also
   exhausted turns after reading the right DM, so discovery cost was
   already borderline at 157 messages.
   (d) *FREEBIEs.* fee-dispute's cutoff_date was stated verbatim in the
   instruction; challenged_by/challenge_date are one Gmail search.
   client-departure's matter_closed/termination dates are one Clio/Gmail
   call each (0.50 with format under the old weights).
   Actions (graders never weakened): DM `traffic` semantics became
   expected-exchanges-per-workday so rates exceed 1 — Grace<->Samuel at
   2.1 yields a 407-message thread with the correction buried at
   position 345 (200+ before, 40+ after), the other nine pairs carry
   100-171 messages (1,680 DM messages total), and `slack_read_channel`
   now caps at 100 messages per call (Slack-like page size), so an
   end-to-end DM skim costs 20+ calls while oldest/latest windowing
   around the clerk-call week stays cheap; the June-16 recap gained the
   fair pointer ("Grace was chasing the clerk's office ... we'll
   confirm ... when she is back on") and audits gate all of it (>=1200
   DM messages, >=350-message thread, burial position, breadcrumb text,
   plus the existing no-leak checks). fee-dispute: instruction no
   longer states the cutoff date; deliverable extended with per-entry
   Clio activity ids (the server's positional id space, reproduced by
   the solver) and minutes_by_timekeeper; near-miss decoys added on
   every side of the join (a cutoff-day data-room entry, post-cutoff
   diligence-worded entries on the Lumen and Solstice matters, a
   post-cutoff Meridian scope-expansion entry without the wording);
   weights recut so the trivially-earned subset caps at 0.30.
   client-departure: deliverable extended with the Slack ts identities
   of the happy update and the first negative signal (graded on the
   calendar-fixed seconds prefix) and the five-milestone reaction
   trajectory [3,2,1,0,0]; freebie subset caps at 0.40. standard-drift
   and vanished-clause change only through the path fix. Rebuild is
   byte-deterministic, audits all green, solve.sh 1.0 on all five tasks,
   naive baselines 0.21-0.375 (every gap > 0.4), pytest and ruff clean.
   The DM rate change reshuffled the shared RNG draw order, so
   procedural ids shifted: graded supersession ids refreshed
   (msg-000263, msg-000408), `_evidence` blocks updated; storyline ts
   seconds are calendar-fixed by construction and did not move.

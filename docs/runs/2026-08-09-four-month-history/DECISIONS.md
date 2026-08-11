# Decisions — four-month history run

Assumptions and judgment calls made while executing autonomously; each
entry says what was ambiguous and which reading was taken.

## Final Harbor decisions — 2026-08-10

The numbered material below this section is the historical build diary. Where
it discusses five/seven-task suites, exact-set-or-zero grading, or 3x hard call
caps, this final section supersedes it.

1. **The suite has eight tasks, not five or seven.** Fee dispute, client
   departure, billing hygiene, second read, visitor log, operative deadline,
   standard drift, and vanished clause are the canonical set.
2. **Generated databases were stale and were not trusted.** The 9,427-event
   log was checked byte-for-byte, then all task environments were
   rematerialized with the current projectors before truth was refreshed.
3. **Reference floors are metadata only.** Harbor has no task call-budget
   contract, and a hard 3x floor cap confounds answer quality with exploration.
   The final floors are 49, 10, 146, 54, 54, 40, 48, and 199 in task order.
4. **Canonical reward measures answer quality.** Process remains a separate
   trajectory diagnostic. A direct reference therefore earns answer/reward 1
   even though process is zero.
5. **Set grading is partial but certifiable.** Ninety percent of each formerly
   exact set field is Counter-F1 and ten percent is exact certification.
6. **Portable stdio is the supported Harbor design.** The proposed compose
   sidecar was not implemented. Environment-owned state plus fixed wrappers
   provides the required offstage boundary in one shared image.
7. **OpenRouter requires a custom Codex provider.** Provider name
   `hartwell_gateway` forces local compaction; providers named `OpenAI` caused
   Codex to call an unsupported remote compact endpoint.
8. **A 2x Harbor agent-time multiplier is part of the fingerprint.** GLM and
   DeepSeek were still doing valid work at 1,800 seconds. Their timeout cells
   were invalid and were rerun, never scored as zero answers.
9. **Budget projection is normalized by launch size.** A three-cell smoke,
   six-cell continuation, and nine-cell task batch cannot share one raw dollar
   forecast. Observed cost is normalized to full-batch units before the next
   authorization.
10. **The `$25.00` cap is binding.** The authoritative final meter is
    `56.005689513` against baseline `32.2139`. With only `$1.208210487`
    remaining before cap and a `$1.50` reserve, seven task matrices were not
    launched.
11. **No missing or invalid trial is a low score.** The completed fee matrix is
    diagnostic evidence. Seven unlaunched task matrices and model-based Harbor
    checks remain genuinely unresolved pending an explicit budget change.

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
15. **Round-5 hardening: exhaustive-reconciliation components.** Each
   hardened task gains a deliverable that solve.sh computes in one SQL
   pass but that no sampling strategy can guess — exact-id set grading
   (hits minus extras, or all-or-nothing) makes partial surveys score
   zero. (a) *fee-dispute* gains `unsupported_entry_ids` (0.30): the
   Clio activity ids of every Meridian entry in the disputed window
   (after Apr 3 through Apr 30; 34 of 117 matter entries) whose date has
   no same-day email or Slack message naming the engagement under a
   marker rule stated verbatim in the instruction ('Meridian', 'the
   diagnostics acquisition', or '00001'; vague data-room/tranche talk
   explicitly does not count, and the Solstice matter runs a data room
   the same month to make that exclusion earn its keep). Ground truth:
   exactly 5 orphans (Apr 17: 581, 588; Apr 22: 629, 631, 634 — 629 is
   the round-4 scope-expansion decoy). Traps on both sides: Apr 7 is
   supported ONLY inside the Marcus<->Peter DM (search excludes DMs) and
   Apr 21 ONLY by an internal email that never says 'Meridian', so a
   client-name grep over public surfaces lists supported entries and
   zeroes the component. The measured minimal honest tool sequence is
   **32 calls** (3 activity pages at the new Clio-default 50/page cap, 3
   Gmail + 5 Slack windowed marker searches at the new 20-match search
   page cap, 12 DM window reads of which three April lanes exceed 100
   messages and cost two reads each, plus discovery, cutoff, challenger,
   write, finish) — above the 30-turn budget for any one-call-per-turn
   strategy; batching models can still land it. Weights recut so the
   round-4 join subset (total_minutes, entry_count, entries,
   minutes_by_timekeeper) caps at 0.45. (b) *standard-drift* becomes a
   per-NDA certification: the corpus grew to NINE vendor NDAs (five new
   conforming histories — Trueline, Cobalt, Harborlight, Brightwater,
   Summit — authored as fabric with NO covering mail, so the email trail
   enumerates only four of nine) and `ndas` maps every exact iManage
   path to conforms/deviates, graded all-or-nothing at 0.55: one wrong,
   missing, or invented NDA caps the score at 0.45. The round-4 clause
   blocks survive unchanged (LexiPoint v2 term flip, Ironclad v2
   residuals add, same markers) at recut weights. Judgment call:
   Ironclad was born nonconforming on term (v1 inherited five years), so
   the survey grades status only and the clause blocks keep the round-4
   'first departure on each clause' attribution (LexiPoint v2). (c)
   *vanished-clause* gains `clean_documents` (0.25): the exact 16-number
   set of multi-version iManage documents that lost nothing
   ({1,2,3,4,7,9,10,11,13,14,15,16,17,18,19,21}; the corpus grew to 17
   multi-version documents via the new NDAs), graded as set equality —
   attestation by enumeration, so finding the Lumen drop without
   surveying the corpus cannot produce the list. (d) Fabric and tool
   changes behind the floors: two standing DM pairs appended to genesis
   (Grace<->Peter 0.6, Marcus<->Sofia 0.5 — appended last so the
   original ten pairs' seeded draws and message content never move; the
   S5 burial stayed exactly 407/position-345), deterministic April DM
   lanes (data-room sprint in Marcus<->Peter with the two dated
   client-naming exceptions, prebill lane in Anita<->Carl, records lane
   in Grace<->Peter; all other lane lines matter-blind by construction),
   slack_search_public capped at 20 matches/page and Clio
   list_activities paginated at its product-default 50/page — the same
   serve-the-product-default pattern round 4 used for
   slack_read_channel. (e) client-departure and operative-deadline keep
   their round-4 designs; the DM fabric they share grew (12 threads,
   2,157 messages), which raises operative-deadline's enumeration cost
   by ~2 reads, and the minted-id refresh after the rebuild moved the
   graded clerk-notice prefixes to msg-000266/msg-000400 (calendar-fixed
   ts prefixes did not move). Graders only got stricter: every round-4
   check survives at equal or lower weight; the new components only add.
   Rebuild is byte-deterministic (2,238,034 identical bytes), audits all
   green (orphan count, DM-only and oblique-only support days, 9-NDA
   corpus, 17-document clean list, >100-message April lanes), solve.sh
   1.0 on all five tasks, naives 0.19-0.30 against gates > 0.4 below
   solve, pytest and ruff clean. Content spend: 5 LM calls (the five new
   NDA bodies); every other record change is code constants served from
   the warmed cache.
16. **Closing verdict — bar not met, and why that is the honest result**:
    the final defect-free matrix leaves 2/15 cells under 0.5. Continuing
    to tune the harness (call caps chosen after observing model call
    counts) would defeat models by goodharting our own benchmark, so it
    was ruled out; the a-priori call-budget policy is documented in
    REPORT.md as the v2 design. Difficulty claims from rounds with live
    environment defects were treated as invalid throughout.
17. **Round-6 call-budget policy (declared before any measurement).**
    Written before any floor was scripted or measured, before any round-6
    record change, and before any round-6 probe, so the policy cannot be
    tuned against observed model behavior. Policy: an episode's tool-call
    cap is **3x the reference tool-path floor** for its task. The floor is
    the call count of the honest MINIMAL tool sequence — the discovery
    path an informed professional who knows the tools (but not the
    answers) would take through the MCP surface — implemented as a
    scripted client driving the real servers and counted mechanically,
    one tool call per step, no parallelism credit. Each task's floor is
    measured once, after that task's round-6 record changes are final,
    and `[harness] max_tool_calls = 3*floor` lands in task.toml before
    that task is probed. Anchoring rationale: the cap is a property of
    the TASK (its record and its tool surface), not of any model — it is
    uniform across models, derived from a reproducible script committed
    with the task, and never adjusted after observing a model's call
    count. 3x is declared here as the standing multiplier: it forgives
    honest wrong turns, re-reads, and schema discovery at every step of
    the reference path, but it prices exhaustive corpus walks (hundreds
    of parallel calls per episode in rounds 1-5) out of the budget. The
    harness enforces the cap as a total-tool-calls ceiling with stop
    reason `call_budget`; tasks without the key keep unlimited calls
    (turn budget only), so prior tasks' semantics are unchanged unless
    their task.toml opts in. This is the a-priori policy REPORT.md
    priced as the v2 design; entry 16's goodharting bar is met because
    the multiplier, the floor definition, and the enforcement mechanism
    are all fixed here, in advance, task-anchored, and model-blind.
18. **Round-6 changes: reconciliation components in the four open tasks,
    measured floors, enforced budgets.** Fee-dispute's round-5 shape (an
    exhaustive-reconciliation component, exact-id all-or-nothing, the
    non-reconciliation subset capped under 0.45) held 2 of 3 models
    under 0.5, so round 6 replicates it everywhere and enforces entry
    17's budgets.
    (a) *Harness*: agent_loop enforces a total tool-call ceiling
    (executed calls; write_file and finish included; calls past the cap
    answered with an error, stop reason `call_budget`); cli.py reads
    `[harness] max_tool_calls` from task.toml (absent key = unlimited,
    prior tasks unchanged); five new harness tests.
    (b) *Floors* (datasets/hartwell/measure_floors.py, a scripted client
    driving the real MCP servers one call per step, each sequence
    asserting it reproduces the task's ground truth): client-departure
    11, fee-dispute 33, operative-deadline 40, standard-drift 48,
    vanished-clause 110; caps at 3x: 33/99/120/144/330.
    (c) *fee-dispute*: the orphan set grew to 6 (a round-6 Apr 28
    consent-tracker entry, id 697, on a day carrying same-day-oblique
    near misses: a deal-flavored consent email and a Lumen chat, none
    naming the engagement); the component is now all-or-nothing at 0.56
    (partial lists score 0), non-reconciliation subset 0.44.
    (d) *standard-drift* gains `silent_versions` (0.28, all-or-nothing):
    the June vendor re-papering lands substantive riders (return-of-
    materials / non-solicitation code constants — playbook-neutral, so
    the survey's calls never move) as v3s across the corpus; exactly
    four have no same-day vendor-naming email (Trueline LEGAL!10.3,
    Cobalt 13.3, Archway 15.3, Summit 21.3) against covered
    (LexiPoint/Ironclad v2, BayMark/Harborlight v3), a notices-only
    Brightwater v3 (real diff, not substantive), Summit's day-after
    email trap, and a wrong-vendor email on Archway's day. Survey recut
    to 0.35; non-reconciliation subset 0.37.
    (e) *vanished-clause* gains `unreviewed_revisions` (0.30,
    all-or-nothing): a 28-message document-mention fabric (public-
    channel notes naming documents on their save days, all code
    constants) covers most of the corpus's ~40 revisions; exactly five
    days stay silent — litigation-hold v2 (LEGAL!4.2), BayMark NDA v2
    (11.2), the dropping Lumen v4 (12.4 — the drop was never
    communicated, which is the story), Lumen SOW v3 (14.3), Archway NDA
    v2 (15.2) — with day-after mention traps (hold 05-07, SOW 05-27)
    and a matter-not-document trap ('Lumen file' chat on the drop day).
    The rule (DOC_MENTION_MARKERS: how the firm names each file; email
    text/attachment filenames plus public channels) is stated in the
    instruction and applied identically by audit, grader truth, and
    solve.sh. clean_documents recut to 0.27; non-recon subset 0.43.
    (f) *client-departure* gains `unanswered_client_emails` (0.56,
    all-or-nothing): the client correspondence fabric grew to 11 Tom
    Hollis emails; the thread anti-join (answered = firm-side message
    later in the SAME Gmail thread) leaves exactly four unanswered
    (msg-000310, msg-000371, msg-000448, msg-000557) against traps: a
    next-day in-thread reply (answered), one reply after a double-send
    (both answered), and the status memorandum sent the evening of the
    third nudge in a NEW thread (answers nothing under the rule).
    Non-reconciliation subset 0.44.
    (g) *operative-deadline* gains `stale_calendar_refs` (0.56,
    all-or-nothing over mixed ids, Gmail exact / Slack ts seconds-
    prefix): exactly five communications cite a superseded hearing date
    after its supersession — Sofia's Apr 21 outline (April 28), her May
    15 courtesy-copies chat (May 20; Grace's reply corrects her and is
    NOT stale), Victor Crane's Jun 12 logistics email (June 18; nobody
    replies, because an email correction would leak the operative date
    out of the DM), Sofia's Jun 15 binder chat (the 18th), and the Jun
    16 recap. The correction chain is causally airtight: Sofia keeps
    working from the last correction she personally received.
    Non-reconciliation subset 0.44.
    (h) *Deviations from the brief*: the brief said "anti-join over 12
    docs" for vanished-clause — the built corpus holds 17 multi-version
    documents and the anti-join runs over all of them; the brief's
    "partial orphan lists score <= 0.3" is met by making the component
    all-or-nothing (partials score 0). Rebuild is byte-deterministic
    (2,291,284 identical bytes), zero LM content calls (every addition
    is a code constant), audits extended and green (exact 6-orphan set,
    silent-versions set, unreviewed set, unanswered set, stale set),
    solve.sh 1.0 on all five tasks inside the harness's grading
    contract, naive baselines 0.10-0.20 with every gap > 0.4, minted-id
    refreshes applied (clerk notices now msg-000272/msg-000413,
    challenger msg-000389, arc ts prefixes unchanged), full pytest and
    ruff green.
20. **Environment bundle split, and instructions that read as work.** Two
    architectural defects, fixed together because they are the same
    defect seen from two sides: the agent could see the machinery.
    (a) *The tool databases were in the agent's own directory.*
    `materialize` wrote `.mcp.json`, `environment.toml`, `state/*.db`,
    and `files/` into one directory that became `/home/agent/workspace`,
    so an agent could read `state/gmail.db` with sqlite and skip the
    emulated products entirely — every discovery cost the tasks are built
    around (paging, DM enumeration, per-day mail checks) was optional.
    `materialize(world_log, out_dir, *, seat=None)` now emits a bundle:
    `environment.toml` + `mcp.json` + `state/` at the root, and
    `workspace/` beside them holding only the document files (moved from
    `files/{workspace}/{basename}` to `workspace/{workspace}/{basename}`,
    the professional's own folders). `MaterializedEnvironment` carries
    both `bundle` and `agent_workspace`. The harness follows the split:
    `open_workspace(bundle_dir)` reads `bundle/mcp.json` and launches the
    servers with cwd=bundle; `run_episode(agent_root, ...)` is handed
    `bundle/workspace`, so `write_file` cannot reach the root above it;
    `cli.py` copies the whole bundle per attempt. In-container the same
    split is a permission: `state/` lands at `/home/environment/state`
    mode 0700, the servers launch behind `run-as-environment`, and
    `/home/agent/workspace` holds nothing but documents (Dockerfile
    comments carry the wiring). The per-task built directory is
    `bundle/` rather than `workspace/`, so the nesting reads
    `bundle/workspace` instead of `workspace/workspace`.
    (b) *Oracle access is deliberate.* `solution/solve.sh`, the
    baselines, and the graders run with `bundle/workspace` as cwd and
    open `${WORKBENCH_STATE:-../state}`; `grade_episode` exports the
    absolute path. They are the verifier and the reference answer —
    offstage by design, and reading the projections directly is what
    makes ground truth reproducible and grading cheap. It is not a claim
    about solvability: that MCP-solvability claim is proven separately by
    `measure_floors.py`, which drives the real servers one call per step
    and asserts each sequence reproduces the task's ground truth. The two
    facts are independent and must stay that way — a task is only
    shippable when the floor script can reach the answer through the
    products.
    (c) *Instructions leaked the scaffolding.* Every `instruction.md`
    told the agent it was working "in this workspace", named `.mcp.json`,
    "the underlying SQLite databases under `state/`", "repository files
    under `files/`", and spelled out epoch arithmetic (`time // 86400`) —
    that last one obsolete since entry 12 made the servers serve true
    calendar dates. All seven were rewritten as a colleague's brief: same
    persona, same business stakes, same mechanical rules, same
    deliverable filename and JSON shape, with the firm's systems named
    only as products the professional has. Certification language was
    re-phrased as a professional standard ("you are certifying this list
    to the partners") rather than a scoring rule ("only the exact set
    earns it"): identical semantics, no evaluation framing. Graders,
    ground truths, and weights are untouched, and the rebuild is
    byte-identical, so every task's solve/naive/missing/determinism
    result is unchanged.
    (d) *Enforced, not asserted.* `datasets/test_instruction_immersion.py`
    scans every `datasets/*/tasks/*/instruction.md` for the banned
    vocabulary (mcp, sqlite, `state/`, `.db`, epoch, day 0, 86400,
    grader, ground truth, reward, eval) and fails the build on a leak;
    `test_agent_workspace_holds_no_environment_internals` asserts the
    agent workspace contains no `*.db`, no `mcp.json`, no
    `environment.toml`, and that `state/` is a sibling of `workspace/`.
    A new task cannot regress either property silently.
21. **Round-7: three mined tasks finished, and one vein retired on
    evidence.** The brief named three veins (billing hygiene, DM
    disclosure, response latency) and allowed replacing any that came up
    empty. Two were replaced; the reasons are the finding.
    (a) *billing-hygiene-audit* (completed from the dead agent's
    half-build) certifies `unsupported_entry_ids` (0.56, all-or-nothing):
    the presence anti-join over all 1,427 Clio activities — an entry is
    unsupported when its timekeeper sent no Gmail message and no Slack
    message, channel **or DM**, on the entry's own date. Exactly 7 entries
    across 4 silent person-days (164; 1150, 1161; 1244, 1249, 1250; 1409),
    438 minutes, two timekeepers. The decoys are single-surface: 77
    entry-days whose only footprint is a DM chat search never returns, 13
    supported by one email, 59 by one public-channel line — a
    Gmail-plus-channels survey reports 84 exceptions (7 true, 77 false).
    `phantom_note_ids` (0.10) applies the identical rule to the 178 Clio
    notes and lands on the same silent days. Non-core subset 0.44. The
    half-built grader and ground truth were sound and are shipped as
    found: the ground truth was re-derived from the built bundle and
    reproduced exactly, and the grader's bare `except TypeError,
    ValueError:` — which reads as a Python-2 relic — is valid on the
    3.14 the Dockerfile pins (PEP 758), which is why ruff normalizes a
    parenthesized rewrite straight back to it. What the dead agent
    actually left missing was structural: task.toml, tests/test.sh, the
    naive baseline, the task test, and a measured floor.
    (b) *dm-disclosure was empty, by construction.* The vein asked for DM
    messages disclosing matter facts to someone off the matter team. The
    whole DM fabric is matter-blind on purpose (entry 15d: the lane lines
    "are deliberately matter-blind"), so a query over all 2,157 DM
    messages for any of the ten client markers returns **two** hits, both
    inside the Meridian deal team — zero disclosures. Replaced with
    *second-read-audit*: the firm's one standing quality control is asking
    a colleague privately to read a draft before it goes out, and
    `unanswered_request_ts` (0.56, all-or-nothing over Slack ts seconds
    prefixes) is the exact set of those requests that drew nothing back.
    78 requests across the 12 lanes; a request is answered when the person
    asked comes back to the asker — later in that same lane, or by email
    to them — by the end of the next working day. Exactly 4 got neither
    (142725, 3424884, 6358735, 8613201). Four readings, four different
    answers: same-day-only lists 10, ignoring mail lists 5, counting
    calendar days instead of working days lists 6 (two Friday requests
    answered on the Monday), and only the stated rule gives 4.
    (c) *response-latency was built, probed, hardened, re-probed, and
    retired.* The vein is real — a thread anti-join over the whole mailbox
    leaves exactly 4 inbound messages that the firm answered later than
    the end of the next working day (msg-000259/000380/000389/000534),
    against 103 never-answered decoys and 2 replies landing exactly on the
    standard. But both sides of the join sit on surfaces Gmail search
    returns: the measured floor is 12 calls (directory + 9 thread pages +
    write + finish), the smallest in the suite. Luna scored **0.88**,
    reproducing the reference path exactly and missing only two counts.
    Hardening (a brief that no longer pre-classifies the decoys, and the
    core recut onto the dated exception report — the exact set of
    (id, received, answered) triples, all-or-nothing, which strictly
    implies the old id-only core) changed nothing: **0.88** again, with
    the dated triples all correct. The honest conclusion is a property of
    the record, not of the wording: **a vein whose anchor and coverage
    both live on search-returnable surfaces is not defensible against the
    strongest model at any instruction quality.** Retired rather than
    shipped as a known-failing task.
    (d) *visitor-log-audit* replaces it, on the vein that survives:
    enumeration of the direct messages chat search cannot reach. The
    reception sign-in sheet is a record class in the firm's own retention
    policy, and `open_handover_ts` (0.56, all-or-nothing) is the exact set
    of requests for its return that were never closed inside the same
    next-working-day standard — 6 of 74 requests (1421855, 5761271,
    6279449, 8006603, 8602820, 9909456), with 62 closed the same day, 6
    closed the next working day (one of those by mail, not chat), a
    same-day reading listing 12 and a chat-only reading listing 7.
    (e) *Deviation, stated plainly*: the brief asked to keep system-pair
    coverage distinct, and second-read and visitor-log share their pair
    (Slack DMs x Gmail) and their mechanics. That is a consequence of (b)
    and (c): after the disclosure vein came up empty and the mail-latency
    vein proved model-solvable, the record offers exactly one structure
    that defeats the strongest model — an anchor inside the DM fabric with
    a precise cross-surface window rule — and the two tasks draw different
    anchors (78 draft-review requests vs 74 sign-in-sheet requests),
    different answer sets, different personas and different trap
    structures from it. Mining a genuinely distinct third pair was
    attempted and measured against the built bundle before giving up:
    standup-vs-timesheet (788 of 895 unmatched), matter-day silence (189),
    matter-note silence (40), telephone-conference contact (229 of 240),
    iManage-version-vs-timesheet (4, all of them the two people who never
    bill), superseded attachments (6 attachments in the whole record),
    reply-all drops (2), cite-check pickups (17-message anchor on a
    searchable channel), and fee-earner days worked but not billed (0).
    None yields a 3-8 set with heavy near-miss noise on an
    enumeration-expensive surface.
    (f) *Floors and budgets* (entry 17 policy, measured after each task's
    record was final and before any probe of that task): billing-hygiene
    85, second-read 53, visitor-log 53 — caps 255/159/159 in task.toml.
    Each floor is a scripted client on the real servers, one call per
    step, asserting it reproduces the task's ground truth;
    `measure_floors.py` gained `_all_activities`, `_conversation_listing`,
    `_read_all` and a shared `_one_to_one_request_audit`. No record change
    of any kind was made: every ground truth is a query over the existing
    world log's built bundle, and zero content calls were spent.
    (g) *Probes* (6 of the 12 permitted episodes, 0 of the permitted
    content calls; 1 attempt each, so these are best-of-1 and the
    best-of-3 matrix is still owed): billing-hygiene 0.13 Luna (finish,
    104 of 255 calls — swept mail and the public channels, opened no DM,
    and reported the 84-exception public-surfaces list the naive baseline
    reports) and 0.00 DeepSeek (max_turns at 30 with 84 calls and 11.0M
    prompt tokens — drowned in the corpus and never wrote the
    deliverable); second-read 0.11 Luna (finish, 61 of 159 — enumerated
    the lanes but closed the window at the end of the day of the request);
    visitor-log 0.11 Luna (finish, 74 of 159 — same failure); and
    response-latency 0.88 Luna twice, which is why it is not in the suite.
    Every shipped cell is far under the 0.5 bar; the retired one never
    got near it.
22. **Evidence population is now a generation contract, not a report claim.**
    Each Harbor task declares `[metadata.evidence]`: the primary retained
    workpaper, exact record count, optional nested source-ID fields/count, and
    joined product surfaces. `build_tasks.py` validates that typed contract
    against the fresh restricted-oracle output before canonical-byte comparison
    and before Harbor staging. Current contracts span 5/47 fee day/entry items,
    655/4,233 billing person-day/activity items, 75 second-read requests, 71
    custody requests, 16/4 NDA version/email items, and 57/53 document
    revision/communication items. An intentional truth refresh can no longer
    silently bless a smaller task without updating a reviewable scope contract.
23. **Fresh model evidence separates real difficulty from specification
    defects.** Standard drift was easy for all models; its repeated remaining
    miss was the Harborlight v2 date because iManage exposes UTC and the oracle
    uses the firm's Pacific calendar. The instruction now states
    `America/Los_Angeles` and the conversion explicitly. Operative deadline
    produced repeated 0.4633 partial answers, but Luna reached 0.818 and
    DeepSeek reached 1.0 by completing the private-correction/stale-reference
    chain. Neither compact task is a defensible hardness win. In contrast,
    second read produced three valid Luna answers at 0.2886/0.2886/0.1219: the
    two 0.2886 answers got the full exception summary right but only one of 75
    workpaper rows, proving the ledger scores professionally retained evidence
    rather than an arbitrary trap.
24. **A launch forecast is now an in-flight authorization.** The second-read
    batch was admitted at `$4.00` after two roughly `$3.5` nine-cell batches,
    but six long GLM/DeepSeek trajectories drove its settled cost to
    `$12.940024093`. They were manually cancelled before the reserve and remain
    invalid. Commit `8e47e9c` runs paid commands in a dedicated process group,
    polls authoritative credits every 30 seconds, and terminates the group when
    observed in-flight cost exceeds the launch authorization or reaches the
    pre-reserve boundary. Pre/post metering and settled-cost forecasting remain;
    live cancellation closes the discovery gap.

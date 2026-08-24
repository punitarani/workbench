# Fixes measured but not applied

Changes inside `_ENGINE_SURFACE` cannot be applied while a recording is in
flight: the fingerprint keys the resume, and editing one of the seven files
means the run in progress can never be continued. So a fix found mid-record
is measured, written down here with its evidence, and applied at the next
restart.

Each entry states what it changes, what it was measured to do, and — the
part that is easy to lose — **what it was measured NOT to do.**

## wake-phase: spread the cohort across the day

`src/simulation/gm/grounded.py`, in the day-planning branch:

```python
# was
slots = quantum // grid
...
wake_delay = plan.day_start + phase * grid

# is
PHASE_STEP = 60  # module level
slots = max(1, quantum // PHASE_STEP)
...
wake_delay = plan.day_start + phase * PHASE_STEP
```

**The defect.** With `wake_grid_minutes` at 90, every persona whose check
interval is at or below 90 gets `quantum == grid`, so `slots == 1`, so
`phase = seed % 1 = 0`. Measured on v7: **21 personas, 323 distinct wake
timestamps, all 21 on every one.** The firm acts in lockstep seven times a
working day. The phase code executes and cannot return anything but zero.

**Measured to fix:** piloted as a real 3-day recording in an isolated
worktree. 45 timestamps, **one persona on 43 of them** — 09:01, 09:13,
09:14, 09:20, 09:24, 09:34, 09:44, 09:49.

**Measured NOT to fix: reply latency.** The same pilot leaves it at a
median of 0.08 hours, 11 of 12 replies under five minutes, matching the
unfixed world. 21 personas over a 90-minute quantum is a wake every 4.3
minutes, so the next persona is always about to wake whether they are
stacked on one instant or spread across the hour. **A five-minute reply
needs a persona to decline its first opportunity — a response delay drawn
per message — which is a behaviour change, not a scheduling one.**

Expect it to move `slack.offhours_share` (0.034 against ≥0.15) and the
firm's temporal texture generally. Do not expect it to move
`email.reply_latency_median` or `email.thread_depth_median`.

### Piloting a change to a frozen file

Use a git worktree so the running recording's tree is untouched — and run
the pilot with `PYTHONPATH` on the worktree's own `src`. The worktree
symlinks the main `.venv`, whose `workbench.pth` points at the *main* tree,
so without it the pilot imports the unpatched engine and faithfully
reproduces the defect it is meant to fix. The tell is an "after" number
identical to the "before" one.

## calendar front-loading: why 77% of invitations are never answered

`calendar.rsvp_needsaction` reads **0.772** against a band of ≤0.1, and it
has been the largest single band failure all along. It is not a persona
behaviour problem.

Split the 2,731 attendee-invitations on v7 by how far ahead the event is:

    lead time         invitations   answered
    in the past                18       0.0%
    within 14 days            289      65.7%     <- inside the 0.6-0.8 band
    beyond 14 days          2,424      17.7%

**When a persona can see an invitation, it answers at 66% — the realistic
rate the band asks for.** `working_memory._INVITATION_HORIZON` is 14 days,
so anything further out never enters the pending list and cannot be
answered at all. And the median lead time is **85 days**: every occurrence
of every recurring series is created at day zero with its own future start,
so on day one a persona is invited to a meeting three months away.

That reframes the fix. Widening the horizon is the wrong move and the
history says why — the horizon was *added* because an unbounded pending list
had personas working through 113 RSVPs a day and chat collapsing to 0.36x.
The problem is upstream: **create each occurrence near its date rather than
all of them at day zero.**

It also explains why surfacing invitations at all — the earlier fix that
took `needsAction` from 93% to 77% — moved it so little. That fix was
correct and it could only ever reach the 11% of invitations inside the
horizon.

Not applied here because it lives in the workplace compiler and changes the
compiled spec, so the config hash moves and the run in flight cannot be
resumed either way.

**Expect it to move** `rsvp_needsaction`, `rsvp_accepted`, and the
`calendar.event.scheduled` rate's shape over the epoch. **Do not expect it
to move** `rsvp_tentative` or `rsvp_declined`, which are 0.000 and 0.004:
the firm having exactly one RSVP verb is a separate defect, and this one
does not touch it.

### how much of the failure this actually explains (measured 2026-08-23)

Less than the entry above implies, and the difference is a measurement
artifact rather than a behaviour. `compile.py:282` expands a standing
meeting across **the whole declared epoch** and emits every occurrence as a
*genesis* event — 520 of v6's 575 `calendar.event.scheduled` events are at
simulated second 0. A recording that stops early therefore carries
invitations to meetings that never arrive:

    every invitation in the log                     2,768   needsAction 0.669
    events starting before the recording ends       1,526   needsAction 0.444
    events starting after the recording ends        1,242   needsAction 0.944

**45% of all invitations are for meetings past the end of the recording**,
and they are unanswerable by construction — a persona cannot RSVP to a
meeting the world never reaches. They drag the headline from 0.444 to
0.669 and none of that is the firm behaving badly.

So the fix has two separable effects and only one is a fidelity gain:

* it removes the unanswerable 45% from the corpus, because an occurrence
  created near its date is never created at all when that date is past the
  recording's end. That is bookkeeping, and the honest way to see the same
  thing today is to compute the band over answerable invitations only.
* it lets the remaining invitations be answered at the rate personas
  already manage inside the horizon — 65.7%, which is inside the band the
  metric asks for.

Best estimate after the fix: `rsvp_needsaction` around 0.34, from 0.669.
**Better, and still failing a band of ≤0.1.** Whatever else is wrong here
is not front-loading, and the entry as first written would have claimed the
whole gap.

The band arguably wants a companion change too: counting invitations to
meetings the recording never reaches measures the epoch's declared length,
not the firm.

## one RSVP verb: the capability is there, the behaviour is not

`rsvp_tentative` 0.000 and `rsvp_declined` 0.004 against bands of 0.05–0.15
each. This is **not** a missing capability. The payload accepts
`accept | decline | tentative`, the persona program's own prose names all
three — *"set response to accept, decline, or tentative"* — and on v7 the
personas chose:

    accept      608
    decline      12
    tentative     0

**A hypothesis, tested and refuted.** The obvious story is that a persona
declines when it has a conflict, and this firm barely has conflicts — the
same absence that retired `double-booked-week` at 5 clashes. Measured:

    response     answered   of which the person had a clashing event
    accept            608     4   (0.7%)
    decline            12     0   (0.0%)
    tentative           0     0

**The twelve declines had no conflict at all**, so the absence of clashes is
not shown to be the cause of the missing verbs, however well it fits. Both
facts are true and the link between them is not established — the second
time in this session that a plausible chain between two real defects turned
out to be invented, after the wake-lockstep and the reply latency.

What is left is a behaviour question with no measured cause: personas accept
98% of what they are asked to, and never hedge. Worth a prompt-level
experiment before anything structural, and worth doing *after* the
front-loading fix above, because a persona answering an invitation to a
meeting three months away has little reason to say anything but yes.

## peer review is a constant function of the reviewer

`grounded.py:770`, in the branch that hands a person a colleague's file:

    elif phase == 1 and colleagues:
        candidate = colleagues[offset % len(colleagues)]

`offset` is the person's index in the sorted roster. It never changes.
`colleagues` is every document written by somebody else, in creation
order, and passes 17 entries on the first day — so `offset % len(...)`
**is** `offset` for the whole run. Every person is permanently assigned one
file to review, picked by their alphabetical rank.

Measured on the v6 record -- **68 days**, 2026-01-05 to 2026-04-08. (An
earlier version of this entry called it "the six-month record", conflating
the 180-day epoch with what was actually recorded. The rates below are
unaffected; the corpus is 2.7x smaller than I said.)

    review versions (author != creator)                139
    reviewers                                           18
    distinct documents ever reviewed          17 of 451  (4%)
    reviewers whose reviews are ALL one document    12 of 18
    median share of a reviewer's reviews on one file    100%

**v7 has it too, and has already locked.** Measured on the live recording
at day 57 of 180:

    distinct documents ever reviewed           30 of 325  (9%)
    reviewers reviewing exactly one document        6 of 21
    median share on their top document                  75%
    days since any reviewer was handed a NEW document    26

The last figure is the one that matters. `colleagues` only ever grows by
appending, so once the file room passes the roster size -- inside the first
day or two -- `offset % len(colleagues)` **is** `offset` and the pick
freezes. The handful of switches visible early (one reviewer runs
2 -> 28 -> 70 across the first three weeks) is the wrapping phase before the
lock, not variety. For v7's remaining 123 days, **no document that does not
already have a second reader will ever get one.**

That also corrects the shape of the claim: the target is the offset-th
colleague document in creation order, and it is permanent from the
fortnight mark -- not literally from the first review.

The branch itself was a fix, and a real one — its comment records that a
firm of seventeen had produced a hundred versions "without a single second
reader". It got second readers. It did not get a second reader for any
document but seventeen of them.

**This is the constant-computing shape**, the subtlest form of capability
without a caller: not dead code, but code that runs, is reached, does
something, and can only ever do one thing. The comment four lines above it
diagnoses exactly this about the *phase* — "authorship never moves once a
document exists, so a phase counted from documents I wrote sticks on
whichever branch it first reaches" — and then the selection *inside* the
branch indexes on a quantity that never moves at all. The lesson was
learned one line up and not applied one line down.

### it is also visible to the personas

A person assigned a file at random writes down that it is the wrong file.
16 revision comments (1.5% of 1,034) say so outright -- "This document is
the firm's Standard Rates table, not the Sable Ridge work product", "No
edit made to this document. The intent requests continuation of the
wage-and-hour..." -- and 8 of `doc-000001`'s 19 versions are that sentence
in different words. The rate card is what the alphabetically-first reviewer
draws forever.

Same class as the reply-with-no-recipient fiction, at a similar scale
(0.8% of events there, 1.5% of versions here), and the same remedy: the
failure has to stop being visible, not be papered over in the prompt.

### the obvious fix makes the visible symptom worse

Replayed offline against the recorded log -- no re-recording needed, since
the log already says which person reached a `sim.deliverable` at which
moment and what the file room held then. 224 review selections:

    rule                       distinct docs   median share   in a directory
                                               on top doc     they write in
    current                          19            100%            13%
    advancing index                 175              9%             4%
    advancing + prefer near         106             27%            81%

An index that advances is the one-line change anyone reaches for, and it
solves the concentration completely -- 19 documents to 175. It also drops
relevance from 13% to **4%**, because a moving index samples the whole firm
uniformly and most of the firm is not your practice. It would have produced
*more* "this is not my matter" comments, not fewer, while the headline
number said the defect was fixed.

Both halves are needed. Preferring colleague files under a directory the
person has themselves written into, then advancing within that pool:

    elif phase == 1 and colleagues:
        # Advance on the same quantity the phase does. `offset` alone
        # never moves, so this line picked one file per person for the
        # whole run.
        moving = (sum(self._world.documents.values()) + offset) // 3
        mine = {
            paths[document_id].rsplit("/", 1)[0]
            for document_id in authored
        }
        near = [
            document_id
            for document_id in colleagues
            if paths[document_id].rsplit("/", 1)[0] in mine
        ]
        pool = near or colleagues
        candidate = pool[moving % len(pool)]
        as_review = True

Documents that ever get a second reader: 19/451 (4%) -> 106/451 (24%).

**What it is not measured to do.** It does not touch how *many* reviews
happen -- 139 review versions is a property of the phase rotation, which
is unchanged, so nothing here moves `document.revised` volume or any
band computed from it. It does not make reviews *good*; a persona handed a
relevant file may still have nothing to say about it. And the 4%-relevance
result for the advancing rule is a caution about this whole file: a fix
measured only on the number it was designed to move can be a regression on
the number that made anyone look.

Not applied: `simulation/gm/grounded.py` is one of the seven files in
`_ENGINE_SURFACE` whose byte digest keys resume, so editing it now ends
the v7 recording. Carry to v8 with the calendar front-loading fix.

## a band that cannot pass, and the world gap behind it

`email.machine_share` counts messages whose sender is the literal string
`"system"`, against a floor of 0.03. Measured across every bundle in this
repository — four workplaces, 7,273 emails — it reads **0.000 every time**,
and it cannot read anything else:

* every sender id in every world is `per-*`;
* `coherence.py:121` requires each email's sender to be a recorded person,
  so a non-person sender fails the build outright;
* so the band needs a `person.record` whose `person_id` is exactly
  `"system"`, breaking the id convention every other person follows;
* and the predicate is `row[3] not in internal and row[3] == "system"`, so
  that person would additionally have to be *external*.

A metric that can only ever compute one value is the same defect as a test
that cannot fail, in the mirror: this one **cannot pass**. It has been
contributing a permanent FAIL to the band count since it was written, and
that FAIL is indistinguishable in the summary line from a world that is
genuinely missing something.

**But the world gap it points at is real.** A law firm receives automated
mail — ECF and court docket notices, e-billing rejections, calendar
reminders, conflict-check results. No workplace in this repository has
produced a single one, and the reason is upstream of the band: there is no
way to record a non-human correspondent. `PersonRecordPayload.affiliation`
is `Literal["internal", "external"]`, with no notion of a service account.

So this is one fix in two halves, and the halves are separable:

1. *Engine.* Let a workplace declare a service correspondent — a docket
   system, an e-billing gateway — as a recorded party the coherence gate
   accepts. Machine mail then becomes representable, and the firm gains a
   category of document with real downstream uses: a docket notice is a
   deadline nobody typed, which is exactly the kind of fact a task can ask
   an agent to reconcile against what people said in a meeting.
2. *Band.* Match on that declared kind rather than on the string
   `"system"`. Until (1) exists the band should be marked as not applicable
   rather than left to fail, because a permanent FAIL trains the reader to
   skim the failures.

**Do not do (2) alone.** Silencing the band removes the only signal that
the world has no machine mail, which is the finding.

Found by applying `_structural_absences`' own rule to bands outside its
hand-kept list of two — see the same commit for
`calendar.cancellation_share`, which is 0.000 for a different reason: the
tool server can cancel an event (`tools/calendar/server.py:587`) and
nothing in `core/intents.py` can emit a cancellation, so the agent can
cancel meetings and the firm never does.

## the book bands describe a firm twelve times larger than any built here

Sweeping for more bands that cannot pass — the `machine_share` species —
turned up one that is pinned by arithmetic rather than by a predicate:

    book.clients           merrick 10, ashgrove 9     band 120–200
    book.top10_fee_share   1.0 in both                band 0.35–0.55

The second is a consequence of the first. A top-ten share cannot be
anything but 1.0 when the firm has ten clients or fewer, so
`book.top10_fee_share` is not measuring concentration here — it is
restating the client count in another form and failing for it. Unlike
`email.machine_share` this one is satisfiable in principle; it just needs a
world with an order of magnitude more clients than this project builds.

The choice is real and worth making explicitly rather than by omission: a
17-person firm with 10 clients and 37 matters is a coherent thing to
simulate, and a band set written for a 150-client book will fail on it
forever. Either the workplaces grow a realistic book or the `book.*` bands
are marked not applicable at this scale. Leaving them to fail costs the
same as any permanent failure — it trains the reader to skim.

**Two cautions on the sweep that found this.** Only two bundles in the tree
still have a world log their `SOURCE` can reach, so "frozen across every
world" rests on n = 2 and is a prompt to look, not evidence. And frozen is
not the same as broken: `billing.duration_uniform_p` and
`email.reply_latency_uniform_p` are frozen at ~1e-304 and ~1e-182 and both
**pass**, because their bands ask for p ≤ 0.01 — the test wants these
distributions to be conclusively non-uniform, and they are. Invariance is
worth investigating and is not itself a defect.

## a matter's status has a vocabulary and no lifecycle

`grounded.py:1664` accepts any status change whose new value is in
`self._vocab.statuses`. That is a membership test on a flat list: nothing
says which transitions are legal, and nothing is terminal. Measured on v6's
81 status changes across 26 matter/field series:

    transitions into Closed                     16
    transitions out of Closed                    9   (56% of closes undone)
    transitions moving backward through the      13
      lifecycle (Closed->Closing, Closing->Discovery, ...)

`tkt-000009` (Pellumbra cross-border assessment) changes status **twelve
times in three months**, including `Closed -> Closing` on 2026-02-03 — a
matter un-closing into the state before closed — and `Closed -> Active`
seventeen days later. `tkt-000017` goes `Closing -> Discovery` in late
March: a litigation matter that was wrapping up returns to discovery.
`tkt-000024` is *"Firm - billing, WIP and realization"*, a standing
internal matter, and it is Closed three separate times.

Every one of these is a single persona — the responsible lawyer — changing
its own matter, so this is not a coordination failure. It is that nothing
tells the persona, or the referee, that closing a matter means something.

**The minimal fix is not "forbid reopening".** Firms do reopen matters; it
is a real event with real paperwork. Two narrower rules cover the measured
damage:

* `Closed` is terminal for the ordinary path — a change out of it is a
  *reopening*, and should be a distinct intent rather than a status edit,
  so it is rare and legible in the record.
* a transition into `Closed` may only come from `Closing`, and one out of
  `Closing` may not go backwards. `Closed -> Closing` is incoherent in any
  reading.

Which orderings are legal beyond that is a design decision about how this
firm works, and it belongs in the workplace spec next to the vocabulary
rather than in the referee.

**Do not build a task on this.** "Which matters were closed and reopened"
is a plausible audit question and there are 9 instances, which is a
tempting register. It would be grading the simulator, exactly as the
reply-with-no-recipient fiction was — see the entry above, and the earlier
one where a firm wrote policies about a bug for six months. The rule to
apply is the one that dataset already paid for: a task may only grade a
regularity the firm would have if the engine were right.

## nothing anyone says is attached to a matter, and that is why the cross-unit tasks keep failing

Four on-stage payload kinds carry a `ticket_id`:

    ticket.created   ticket.updated   ticket.commented   work.time.logged

All four are **ledger** kinds. Every kind that carries what people actually
say or make has no matter reference at all:

    email.message      chat.message        meeting.transcript
    document.created   document.revised    calendar.event.scheduled
    chat.conversation.created              calendar.response

So this firm's record knows which matter a *time entry* belongs to and
never knows which matter an *email* is about. That single absence is the
reason three separate attempts at a second hard task ran aground, and it
took three failures to see it as one cause rather than three:

* **cross-unit supersession.** Deciding that "Cecile said Thursday here and
  Friday there" is one commitment revised rather than two commitments needs
  both statements attached to the same work. Three cheap ways to recover
  that from unit titles gave three different answers with errors in both
  directions (58%, 17%, and a false negative on a matter-named channel).
* **delegation chains.** A hands to B, B hands to C, and who owes the
  deliverable is only answerable by following the chain. There are 19
  handoffs naming a real colleague across mail, chat and meetings — enough
  rows — and no way to tell whether two of them concern the same work.
* **email supersession** is the same wall from the other side: it exists
  (16 of 127) but every instance is inside one thread, because a thread is
  the only unit whose messages are reliably about one thing.

`live-commitment-register` works *because it side-steps this*. It keys on
(owner, standing meeting), and a recurring meeting is an anchor the record
**states** — an identity, not a subject somebody has to infer. That is a
narrow escape hatch, and it is why the one working task is the one that
found it.

**The fix is an optional `ticket_id` on the communication and artifact
kinds.** The prose stays natural; nobody has to say "re: tkt-000012" out
loud, and the persona prompt already forbids exactly that — *"Never put an
internal id in a path — no `tkt-`, no `doc-`."*

*Corrected, having checked:* a first draft of this entry said the fix was
cheap because "the action specs hand the persona its engagements, so the
intent knows". **The intent does not know.** No communication intent
carries a matter reference:

    EmailIntent          kind, thread_ref, reply_to_ref, draft, attach_document_refs
    ChatIntent           kind, conversation_ref, reply_to_ref, draft
    DocumentEditIntent   kind, document_ref, create, edit
    MeetingSpeakIntent   kind, meeting_ref, text, yields

The action spec offering a list of engagements is not the same as the
persona recording which one it chose, and nothing carries that choice
today. The pattern to copy exists and works — `TimeLogIntent.ticket_ref`
and `TimesheetEntry.ticket_ref` are how the ledger kinds get their link,
including the referee's resolution of a `ticket_ref` and its rejection of a
bad one — but it has to be added at every layer:

    core/intents.py            a ticket_ref on 3-4 intents        (frozen file)
    simulation/persona/programs.py  the prompt that says when to set it  (frozen)
    simulation/gm/grounded.py  resolve and reject, per handler    (frozen)
    core/events/*.py           the field on 3-4 payloads
    tools/*/project.py         project it
    tools/*/server.py          serve it

That is a project rather than a patch, and three of the six files are in
`_ENGINE_SURFACE`. The value estimate below is unchanged; the cost estimate
was wrong by a lot.

### the cheap alternative was tried and it cannot work

Before committing to six layers: `work.time.logged` already carries
`ticket_id`, `person` and `time`. If a person logged time to exactly one
matter on the day they wrote a message, the anchor is already in the record
and no schema has to move. Measured over 707 emails:

    sender logged time to exactly ONE matter that day      0   (0%)
    sender logged time to several matters that day       274  (39%)
    sender logged no time that day                       433  (61%)

**Zero.** Not "few" — none, and it is not a fluke of the window. A lawyer
here works **six or seven matters a day** (the distribution peaks at 7 of
1,410 person-days, and only 3 person-days in the whole record have one), so
a day-level anchor cannot distinguish anything. That number is not a defect
either; it is what the fidelity work was for.

Narrowing to an hour would not help: the timesheet is a single end-of-day
turn, so **94% of person-days have every entry at one identical timestamp**
and 11,014 of 11,127 entries are logged in the 15:00 hour. There is no
intra-day ordering to exploit, by design.

So the anchor genuinely has to be recorded at the moment of writing. The
negative is worth as much as the positive here — it is the obvious first
idea, it costs nothing to check, and it forecloses the "just derive it"
objection to a schema change.

Two cautions, because this one is easy to overdo:

* **Do not anchor everything.** If every message carries a matter, a task
  becomes a filter and the difficulty is gone. People name the matter
  sometimes; the field should be present when the persona was working on
  that matter and absent otherwise, which is also what makes the anchor
  worth reading.
* **An anchor makes retrieval easy and judgement no easier**, which is the
  point. A frontier agent will dump and filter on it — 56–72 shell calls
  against 2–4 tool calls is the measured behaviour — and a task whose
  difficulty is *volume of judgement* survives that where one whose
  difficulty is retrieval does not.

Schema change, so it moves the config hash and needs a fresh recording.
This is the largest single unlock available for the task half of the
project, and nothing else in this file is a prerequisite for it.

## the three probe oracles are orphaned, demonstrated

The world-stamp gate refuses them with "derived from an unrecorded world",
which is an inference from a missing stamp. It is also literally true, and
now measured: of `off-sense-register`'s 22 oracle rows, **6 refs resolve in
`out/merrick/bundle` and 5 in `out/merrick/probe-bundle`**. Neither bundle
on disk is the world that produced them.

Two consequences, and only the first is obvious.

*They cannot be scored against.* The competent-dump technique that settled
the commitment register's floor needs a corpus to build the dump from, and
theirs is gone. So those three tasks keep the floors already measured —
0.363, 0.474 and 0.556 — which remain valid **as arithmetic on that
oracle's shape**, because `baselines.measure` needs only the rows, the
scalars and the grading path. They are not valid as numbers for a v7-built
task, which is what the runbook already says.

*Delete them at landing rather than refreshing them.* `--refresh-truth`
would overwrite an orphan with a fresh key and leave no trace that the
previous one described a vanished world. Deleting makes the next build
`fresh` by the ordinary path, and the stamp it writes then means something.

This is the clearest instance yet of why the stamp was worth adding: the
refusal reads as bureaucratic until you check, and then it turns out the
answer key really was describing somewhere that no longer exists.

## the gpt-5.6-sol tier reaches the gateway now, and its sub-agents stall at 31s

Three sweeps of `live-commitment-register` scored 0.000 on this tier and
none of them was a score. The cause is fixed and the fix is verified; a
second, different failure now stands behind it, and this note exists so
the next person does not re-diagnose the first one.

**What was wrong.** Harbor's hermes agent forwards `OPENAI_BASE_URL` only
on the native `openai` branch, and this tier is not that branch, so the
container got a credential and no endpoint. `exec_as_agent` supplying both
in the environment was enough for the *main* agent and not for its
sub-agents: they rebuild their client from `config.yaml`, which named the
provider and the model and carried neither endpoint nor key. Eighty lines
of `HTTP 401: Missing Authentication header` against the vendor's public
API, every one from a `[subagent-N]`, each "completing" in under three
seconds while the trial looked busy.

**What fixed it.** The endpoint and the key go in the config, under
`provider: custom` — the only provider for which hermes reads
`model.api_key`, and the only one under which it trusts a non-loopback
`model.base_url`. Verified on 2026-08-24: **zero** missing-auth errors and
**zero** requests to the public API, where a comparable trial before the
fix had 80 and 32.

**What is still wrong.** All eight sub-agents now reach the gateway, run
for ~31 seconds each, and report `Interrupted during API call`. Uniform
timing across eight concurrent calls says timeout rather than content. It
is not the gateway's: that allows 180s (`gateway.py`). Candidates not yet
eliminated — a per-call timeout inside hermes' delegation, the eight
concurrent calls exceeding what the single-threaded proxy will serve, or
the `azure` pin on `openai/gpt-5.6-sol` being slower than that budget.

**What it costs.** Nothing that has been asked for. The task bands on
opus-5, glm-5.2 and kimi-k3 without it. It costs the fourth column, and
the aggregator reports the tier as `no deliverable` rather than as a score
— which is correct, and is the only reason this is a note rather than a
number in a table.

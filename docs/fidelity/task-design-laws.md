# What this dataset has learned about building a gradeable task

Every line here was paid for. Each states a rule, the measurement that
established it, and where the detail lives. Nothing is included on the
strength of an argument alone — several entries contradict something that
seemed obvious at the time, which is why the measurement is named.

## About the rule a task grades

**A conjunctive rule is safe only when its conjuncts share a unit.**
`live-commitment-register` first graded "a commitment, on a matter, by a
day" over a *turn*. Speaker and deadline are properties of a turn; which
piece of work a promise is about is a property of a *clause*. Over 71-word
turns they came apart in both directions — 65% of real commitments
discarded for not naming a matter in the same breath, and a third of the
kept rows had the matter name more than 120 characters from the commitment.
An agent reading correctly would have been graded wrong. No care in the
brief turns a regex over a turn into a reader of clauses.

**Both halves of one rule must be specified at the same precision.** The
same brief named its deadline forms as a closed table and gave only an
*example* for the owner form. Opus 5 generalised — correctly, by the
brief's own words — counting "i'm calling their counsel" where the oracle
counted only "i'll have a firm answer by eod". It came out broader on some
turns and stricter on others, 22 rows against 33 with only one of its own
spurious. That is what an unpinned boundary looks like from outside, and
the score it produces measures agreement with a regex.

**Grade the resolved value, not the word that names it.** A deadline said
out loud is relative: `EOD`, `tomorrow`, `Thursday`. Grading the token
hands away the column — the commonest word is 47–69% of live answers
depending on the window, so a reader who never opens a transcript scores
most of it, and *beats* a careful reader who takes each person's first
statement. Grading the resolved calendar date drops the guessing floor to
16–23% and roughly doubles the first-answer error rate, because **the same
words said in a later meeting mean a different date**.

**Anything a brief states, an agent tries to satisfy.** A count of the
answer's own composition is therefore a specification, not colour. Publish
raw match counts over overlapping patterns and a careful reader will write
them into its scratch file as a target and spend its budget failing to
reproduce numbers that are not a partition. Counts of *excluded* material
are safe — reproducing them earns nothing — and are worth publishing,
because they price the obvious mistake.

**A form table written before the corpus is counted describes a world that
does not exist.** Every task in this dataset that admits a list of literal
forms was audited against the record, and every one of them was wrong
somewhere:

    deadline-week-promise-clock   3 of 7 forms grade nothing (end of month
                                  0 messages); and its note claimed the
                                  article form beats the bare form 15-to-0
                                  when this corpus reads 149-to-0 the other way
    no-op-revision-register       1 of 6 forms grades nothing; and all five
                                  decoys it names to exclude appear zero times
    court-clock-computation       its 3 forms match 4 messages in 67 days
    one-sentence-two-dates        its table counts a compound as two dates,
                                  so 13 of its 14 "hits" are one date each

The failures are not symmetric and both directions are expensive: a form
that fires on nothing is a column of nothing dressed as a rule, and a table
that counts one thing twice manufactures rows the world never had.

**And screen with the task's own admitted forms, never a proxy for them.**
A proxy answers a different question and which way it errs is luck. In one
audit a pattern *narrower* than the corpus reported a live task as empty —
one commit from retiring it — and a pattern *broader* than the brief
reported a dead task as viable, which would have shipped it. The narrow
failure is the more dangerous of the two, because absence is the verdict
nobody argues with and retiring a task looks like diligence.

## About the checks around it

**A stale constant in a *gate* is worse than in a solver.** A gate is what
people consult *instead of* looking, so its output is a verdict and a
verdict is not re-derived. A viability screen carried a hand-written matter
list containing two matters the firm never had while missing the third-
busiest handle in the corpus, and a weekday-only deadline regex covering an
eighth of the material. Supersession read 29%; on the forms actually
admitted it was 53%. Derive a gate's inputs from the served source so a
ghost is structurally impossible, and have it print what it could not
reach.

**Derive the answer twice, by genuinely different routes.** Independence
caught what nothing else did, twice in one day on one task: an epoch left
on a fixed UTC offset that disagreed with the timezone on every meeting
after the spring transition, and a compound deadline written with a hyphen
(`EOD-tomorrow`) that resolved a day early. Both produced confident,
plausible, wrong dates. A verifier that shares the solver's expression
reproduces its bugs and then certifies that the two agree.

**A criterion must never floor a correct answer to zero.** `row_fields`
bounded its extra-row penalty against the *oracle's* size, which says
nothing about how much the agent got right, so an answer holding ten rows
correct in every graded field scored 0.000 on a criterion weighted 3 of 11.
Nothing about that zero is a fact about the model.

**A timeout that cuts off honest work measures the clock.** Three trials
reached the wall mid-calibration, having built four competing readings of
the rule and identified the right one, with no time left to write it down.
Downstream that is indistinguishable from a model that cannot do the task.
Time a real read before trusting a number.

## About difficulty itself

**Measured dead on frontier models:** rule difficulty (Opus 5 at 1.000 and
0.976 on two tasks built to punish an editorial reader), coverage
difficulty (bimodal — luck, not skill, and gone once the corpus is bounded),
and procedure difficulty (scriptable; fifteen measured wrong-branch payoffs
across five designs had a **median of 0.90**).

**The one mechanism measured to move a frontier model** is *a second
statement inside a unit the reader has already resolved* — a commitment set
in one meeting and quietly replaced in a later one, which no single meeting
reveals. Grading resolved dates rather than tokens extends it to the case
where the speaker never changed their words.

**Any key component strong enough to collapse row F1 is also a written
instruction for the right method**, and deterministic gradeability implies
programmatic solvability — the agent has a shell and will use it. Frontier
agents do not read a corpus in context: they dump it with the shell
(56–72 shell calls against 2–4 tool calls) and page through it. That moves
the bytes, not the judgement, so a task whose difficulty is *volume of
judgement* survives the shell where one whose difficulty is retrieval does
not.

## About the world the task reads

**An engine failure becomes world data unless the failure stops being
visible to the personas.** A recording refused any reply that named no
recipient; the firm responded by writing a policy, tracking escalations and
reminding each other to read the To/CC line aloud — 0.8% of all on-stage
events, 4.2% of documents, and someone billed time to it. Suppressing what
personas may *narrate* is not enough: a refused action is observable
without any error text. Remove the refusal and the fiction has nothing to
be about; the next recording was clean.

**Read a staged environment's file listing once per corpus.** That is how
the fiction above was found — not by searching for it, but by reading the
document names as a firm's own filing.

---

Detail and measurements: `task-viability.md`. Corpus-transition procedure:
`when-the-corpus-lands.md`. Writer defects: `post-freeze-fixes.md`.

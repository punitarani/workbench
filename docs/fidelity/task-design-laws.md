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

**Print the interface before writing the query.** The proxy law below is
the one most often broken, and a day spent breaking it four times says the
countermeasure is not "try harder". Three of the four were not
screen-avoidance at all — they were *guessing a schema*:

    clio.display_number      read as matter identity; it is the CLIENT, and
                             its distinctive tokens are partner surnames
    Band.low / Band.high     the fields are `min` and `max`; the code fell
                             through to a default and reported every one of
                             36 band failures as missing by exactly 1.0x —
                             the answer that says "no gate needed"
    "carries the bare verb"  read as the off-sense register's rows; its rows
                             are the OFF-SENSE subset, and its own screen
                             says that share is what "only a person reading
                             the sample can set"

Each ran without error and produced a plausible number. The fourth printed
`Band fields: ['label', 'surface', 'min', 'max', 'v1']` in its own output,
two lines above the code that used `low` and `high`. So: dump the field
names, the distinct values, one whole row — *then* write the analysis. It
costs one statement and it is the only thing that catches a wrong field,
because a wrong field does not raise.

**And screen with the task's own admitted forms, never a proxy for them.**
A proxy answers a different question and which way it errs is luck. In one
audit a pattern *narrower* than the corpus reported a live task as empty —
one commit from retiring it — and a pattern *broader* than the brief
reported a dead task as viable, which would have shipped it. The narrow
failure is the more dangerous of the two, because absence is the verdict
nobody argues with and retiring a task looks like diligence.


**The working mechanism does not obviously port to a second surface, and I
could not cheaply establish whether it does.** Supersession is the one
thing measured to move a frontier model, and only one task uses it. Two
things were measured about extending it:

*Email carries supersession, in its easy form.* Over 68 days, 127 people
stated a deadline in a thread and 16 of them (13%) later stated a different
one. Every one of those revisions is **inside the same thread**. The
meeting register is hard because the replacement lives in a meeting the
reader has already closed; a thread is a unit the agent reads in one pass,
so the same rule on email grades retrieval rather than the thing that
worked.

*The cross-unit form needs a matter anchor, and this corpus may not have
one.* Deciding that "Cecile said Thursday here and Friday there" is one
commitment revised, rather than two commitments, requires knowing both
statements are about the same work. Three cheap ways of recovering matter
identity from a unit's title were tried and **all three were wrong, in
different directions**:

    clio.display_number         "00001-CoastalMeridianBancorp" is the client,
                                not the matter; its distinctive tokens are
                                partner surnames
    rare words in description   58% of email subjects "named a matter" --
                                on words like practice, billing and review
    capitalised proper nouns    17% instead, and 0 of 34 chat channels --
                                but `linden-pryor-trade-secret` IS a matter
                                channel, missed because slugs are lowercase

Both over- and under-counting appeared within twenty minutes of each other,
which is the proxy law biting on the person who wrote it down. The result
is *not* "email cannot carry a task"; it is that the anchor has to be built
as carefully as the deadline forms were, and until it is, the numbers above
are not evidence for anything. Anchoring on the *standing meeting* is what
`live-commitment-register` does, and the reason it works is that a
recurring meeting is an anchor the record states rather than one a rule has
to infer.

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

**The dump floor is mostly set by what fraction of the candidates are
answers, and that is knowable before the task is built.** A reader who
reports every candidate has recall 1.0 by construction, so its row F1 is
fixed by precision alone — `2p/(p+1)` where `p` is rows ÷ candidates.
Across twelve tasks in two datasets that predicted quantity correlates with
the measured dump floor at **r = 0.892**:

    rows/candidates   dumped F1   measured dump floor
    0.07-0.15           0.13-0.26        0.36-0.64
    0.28-0.48           0.44-0.65        0.66-0.75
    0.88-0.90           0.94-0.95        0.95-0.99

`client-responsiveness-sla` admits 43 of its 49 candidates, so reporting
everything is 88% right before anything is read, and it pays a dump 0.990.
`workpaper-open-items` admits 55 of 61 and pays 0.954. Neither is a grading
bug: a rule that admits nine candidates in ten cannot punish admitting all
ten. **Keep the answer under about a tenth of the candidate pool** — and
still measure, because the relation sets a lower bound rather than the
number.

*And a hole in it, found by applying it.* The ratio depends on **which
pool the report declares**, and a wider declaration makes the measured
floor look better than the real one. `deadline-week-promise-clock` carries
158 promises. Against every mail message (707) that is a ratio of 0.223 and
a dumped F1 of 0.365; against the messages that carry any relative date
(332) — which is the set a dumper would actually submit, since the task is
about dated promises — it is 0.476 and 0.645. Same task, same rows, two
floors nearly 0.3 apart.

The baseline sizes its dump from the declared count, so declaring the wider
pool *lowers* the measured floor while raising the real one. A task can
therefore pass the gate by naming a generous candidate count. No automatic
measure closes this: bounding the real floor means knowing which
pre-filters are cheap for a reader, and that is a judgement about the
corpus rather than a property of the oracle. Screen a design against the
narrowest pool a competent reader could filter to in one pass, not the
widest one the report happens to name.

*What is not explained.* The measured floor sits above the pure row-F1
prediction by between 0.006 and 0.473, and three attempts to attribute that
gap all failed: share of figures that are tallies of the rows (r = 0.46),
share that are still *paid* tallies (r = 0.32), and paid-scalar weight
share (r = 0.49) — the last on a predictor that is 0.385 for eight of the
twelve, so its correlation rests on four points. On n = 12 none of these is
worth acting on. The gap is real, it is sometimes large, and this file does
not know what drives it.

**A no-comprehension baseline is only a floor if it is the best one a
reader could actually reach.** `baselines.measure` builds its dump as the
true rows plus *random noise*, sized from the task's own read-count. That
is a strawman on two counts: the noise rows match no key, and the
read-count often measures work done rather than candidates a cheap filter
leaves. Both make the floor look lower than it is.

The competent version is buildable per task, and the recipe is general
even though the filter is not:

1. fill the task for a window and run its solver against the bundle — the
   solver's own output **is** the answer key for that window, so no
   committed oracle is needed;
2. build the answer a reader would submit after one cheap pass — for
   `live-commitment-register`, one row per speaker-per-meeting who makes a
   dated first-person undertaking, with the commonest date guess;
3. score both through the task's own `test.sh`.

Measured that way on 30 days of v7, 17 true rows: the strawman scores
0.366 and the competent dump 0.419. The direction is what the ratios
predicted; **the size is a seventh of it**, because row F1 carries 5 of
about 11 weight and the extra-row penalty is capped. *A ratio on one
criterion is not a ratio on the score* — a lesson that cost an hour of
believing a 4.4x row-F1 gap meant a 4.4x floor.

**A floor that is printed and not compared to anything is decoration.**
`build_tasks` measured and printed every task's no-comprehension floors for
months, with a comment explaining that a rollout number must never be read
without them. Nothing compared the number to a threshold. The dataset that
*owns* that code was fine — its tasks measure 0.363–0.556 — and the one
that does not call it pays a dump **0.990** on one task and 0.954 on
another, across seventeen tasks banded on three models with no floor ever
measured. Under the gate now in place, 10 of those 17 refuse and the other
7 warn. Set a threshold, or the measurement is a habit rather than a check.

**And the strongest no-comprehension answer is a bracket, not a number.**
Reporting every candidate scores one thing if the reader also gets its own
counts wrong and another if it is handed the true scalars; both are
defensible and the truth is between them. Which end you quote decides the
conclusion: on `live-commitment-register`, read against the empty-register
floor both measured models look like partial successes, and read against
the top of the dump bracket one clears it by 0.085 and the other sits 0.012
*below* it. Quote both ends, always.

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

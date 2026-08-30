# The commitment revision register

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. The firm's standing meetings are where
dates get set. Somebody says they will have a thing done by a day; a week
later, in the same standing meeting, they say a different day. Neither
statement is written down anywhere except in the transcript of the room it
was said in.

Before the partner meeting you produce the register of **what is still
owed**: who owes something, in which standing meeting they said so, the
date it is due — counting only the most recent thing each person said in
each meeting — and **how many earlier statements that one replaced**.

Those last figures are what the partners actually argue about. A date that
has moved eleven times and a date set once and kept are the same row until
somebody says how far it moved and how often, and nothing in the firm's
systems records either: it is the shape of a chain that exists only across
transcripts.

Note what that asks of you. The **last** statement gives the date owed. The
**first** gives the date originally promised. The **count** gives the
length. A reader who finds one end of a chain and stops has one of the
three and cannot get the other two — they are not derivable from each
other, and none of them is derivable from any system here.

The firm's systems are available through tools: **meetings** (transcripts of
what was said), **clio** (matters, users and time entries), **gmail**,
**slack**, **imanage** and **calendar**.

## Where the answers are

**In the transcripts, and only there.** A commitment made out loud is not a
field in any system. Clio has assignees and statuses; it does not have
"Cecile said Thursday". This register is built by reading what people said.

Mail and chat are not this register. A promise made in an email is a
different act from a promise made in a room, and this report is about the
room. If somebody commits in a meeting and mentions it later in mail, the
meeting is what counts and the mail changes nothing.

## The window and the meetings

Read the meetings held from
****Tuesday 6 January 2026**** through
****Monday 6 July 2026****, inclusive — ****129****
working days and ****512****
standing meetings.

A meeting is in the window when it **started** inside it; one that runs past
the last day is still that day's meeting.

**Only the firm's standing meetings count.** A standing meeting is one that
recurs: its title appears on **three or more days** inside the window. The
firm also holds one-off working sessions, called to settle a single
question; those are **not** part of this register and make no rows, however
much is promised in them. `meetings_read` counts the standing meetings you
opened, whatever was said in them.

## What counts as a commitment

A turn is a **commitment** when the person speaking says **they** will do
something, and names **when**. Both have to be present **in the same
clause** — not merely somewhere in the same turn, and not merely in the same
sentence.

**A clause ends at a full stop, question mark, exclamation mark, semicolon,
colon, or dash.** It does *not* end at "and", "so" or "but": this firm hangs
several verbs off one subject, and *"I'll have it edited and released by
Wednesday"* is one promise with one date.

That boundary decides most of this register, because people here pack a
status report and a promise into one sentence. *"I'm expecting a written
confirmation on target filing dates by end of day — I'll flag it to Priyanka
the moment it lands"* is two clauses: the `end of day` belongs to somebody
else's confirmation and the promise carries no date at all. **No row.** The
same goes for *"Position Statement review, owner Jamal, due EOD tomorrow …
I'll circulate the updated Master Docket Report"*, and for *"if it's still
open Wednesday EOD, flag me directly and I'll make the call"*, which names a
date as a *condition*. A promise whose timing depends on an external event —
*"the second I get a response, I'll log it"* — names no day at all.

Five further things have to be true of the date, and each of them is a way
the same sentence can hold a promise and a day that have nothing to do with
each other:

- **The day comes after the promise.** *"Wednesday it is, Dov, I'll expect
  it closed by then"* recites a date somebody else owns and then promises to
  watch it. **No row** — the deadline is Dov's.
- **The day is attached to the promise**: either a preposition introduces it
  — `by`, `before`, `due`, `on`, `come` — or it ends the clause, as in
  *"I'll have the scope and timeline doc to Clement Thursday"*. **A time of
  day may trail it and the day still ends the clause**: *"I'll check with
  Noor first thing tomorrow morning"* is due tomorrow, and *"I'll push again
  tomorrow AM"* is too. **A time of day may also stand between the
  preposition and the day**: *"by mid-morning tomorrow"* and *"by 4pm
  Monday"* are attached exactly as *"by tomorrow"* is. A bare day sitting mid-clause is naming a thing, not
  a date: *"I'll defer the EOD escalation ownership to you"* hands over a
  task called the EOD escalation,
  and *"someone needs to own the EOD escalation call"* asks for a volunteer.
  **Neither makes a row.**
- **`I'll need` is a request, not a promise.** *"Adaora, I'll need your
  environmental figure by tomorrow"* dates something the speaker is asking
  somebody else to deliver, and this register reports what the speaker
  **owes**. **It makes no row**, however plainly it names a day.
- **Nobody else's clause stands between the promise and the day.** *"I'll
  ping the moment I have it, Mira, so you can finalize the Officer's
  Certificate before tomorrow"* dates Mira's work: the promise is to ping,
  undated. **No row.** A conjunction alone does not mark this — *"…and I'll
  have a firm date before Friday"* and *"…and can report back by EOD"* are
  both still the speaker's own. **A new subject does.**
- **No negation stands between the promise and the day.** *"I'll cross-check
  same day and give you a firm date the moment it lands, so let's not slip
  that to Monday"* refuses Monday; *"closing tomorrow on an unconfirmed date
  is not a real deadline"* refuses tomorrow. **No row for the day being
  refused**, and none for the promise either, since it carries no admitted
  day of its own. **A comma ends a negation's reach**, so *"I'll have a real
  number, not a guess, by end of day"* is a commitment for end of day: the
  `not` belongs to the guess, not to the day. **A negation written as a
  contraction counts the same**: *"I'll make sure Clement doesn't see it or
  hear its substance on Thursday"* refuses Thursday, and *"I'll chase Roland
  again if I haven't heard by Friday"* names Friday inside the condition
  rather than as the day the chase is due. **No row for either.**
- **The day is one the speaker actually picked.** A day offered as one of
  two **times** settles nothing: *"I'll get them to you today or tomorrow"*,
  *"I'll get the joint call with Harriet locked for Wednesday or Thursday
  afternoon"* and *"I'll hold the tracker update until then or first thing
  tomorrow"* each leave the date open. **No row — not for either time, and
  not for the first of them.** What decides this is whether the alternative
  next to the `or` is another *time*. An `or` joining two things to be
  **delivered** leaves the deadline alone: *"I'll have my sign-off or a
  specific open item by Thursday"* is due Thursday, and so is *"I'll review
  the linkage log tomorrow morning and sign off or tell you precisely what
  is missing by Thursday"* — the `or` there offers two ways to answer, not
  two days to answer on. **A fallback marked `at the latest` is a deadline,
  not an alternative** — it is what settles the choice rather than being
  part of it, so *"sent over to you today or tomorrow at the latest"* is
  due tomorrow and *"I'll flag the room the moment I hear back or by end of
  week at the latest"* is due end of week.

**A day named only to rule it out is not a deadline.** *"I'll get an answer
today, not tomorrow"* commits to today, and `today` is not one of the days
this register admits — so it makes **no row**, and certainly not a row due
tomorrow. The same goes for *"urgent, not EOD"* and *"same day, not
Wednesday morning"*. In *"by Wednesday so it's not in Friday's crunch"* the
commitment is Wednesday and Friday is merely the thing being avoided.

- **The speaker is taking it on themselves**, in the first person, about a
  **future** act. In this firm's transcripts that is written `I'll` or
  `I will` — *"I'll get you a clean answer by EOD tomorrow, one of the
  three, no fourth chase needed"*. Nothing looser counts, and two things
  that read like commitments are not:
  - **A report of what is already under way.** *"I'm calling their counsel
    now"* describes present activity and names no future act. It makes no
    row.
  - **Work handed to somebody else.** *"Ingrid, I need a yes/no from them
    directly by EOD, not routed through Quentin"* is an instruction, and it
    makes a row for nobody: not for the speaker, who is not doing it, and
    not for Ingrid, who did not say it. The same is true of a chair
    recapping what other people promised.
- **A day is named.** In the forms this firm actually uses for a near date:
  ***end of day**, written as `EOD`, `COB`, "close of business" or "end of the
  day"; **tomorrow**; **end of week**; and **a named weekday**. Compounds
  occur and each names a single deadline, not two — "by `EOD` tomorrow" is
  one date, the end of the following working day*

Nothing else is a commitment. In particular, **a question is not one**
(*"Anything from either of you I should loop into the Thursday call?"* names a day and
promises nothing), and **a date already past is not one** — a turn reporting
that something *was* done on a day is a report, not a promise.

## Turning what was said into a date

The register reports **dates**, not the words. "EOD" said three weeks apart
is two different obligations, so every deadline is resolved against **the
day the meeting was held**:

- **end of day** — including `EOD`, `COB` and "close of business" — is the
  day of that meeting.
- **tomorrow** is the next working day. Said on a Friday it means the
  following Monday: the firm does not work weekends, and a Saturday
  deadline is a day on which nobody can deliver.
- **end of week** is that week's Friday. Said on a Friday it means that same
  day, not a week later.
- **a named weekday** is its next occurrence, always *after* the day it was
  said. Said in a Thursday meeting, "Thursday" is next Thursday.
- **a compound** such as "EOD tomorrow" is one deadline, not two.
- **this list is closed.** A day named any other way is not a deadline
  this register carries: *"I'll have my markup back to her by end of day
  **the 15th**"* pairs `end of day` with a calendar date, which is not one
  of the forms above, so it names no day here and makes no row.

## Which one is live

**A person makes one live commitment per standing meeting: the most recent
one.**

When the same person commits again in a later meeting of the same series,
the later statement replaces the earlier one entirely. The earlier one is
not a second row, not a note, and not part of the register — it is simply no
longer what they owe. This is true **even when they say the same words**: a
person who said "EOD" a fortnight ago and "EOD" again this week owes this
week's date, not the old one.

**Only a statement that would itself make a row can replace one.** The
rules above discard a great many things people say — a promise with no day
on it, one whose day belongs to somebody else's clause, one that turns on a
condition. None of those is a commitment, so none of them supersedes
anything and none of them counts toward `superseded`. Somebody who set a
date in May and in June said *"I'll update the checklist, with Quentin's
comments due tomorrow"* still owes the May date: the June sentence dates
Quentin's work, not their own, and a person does not stop owing a thing by
mentioning it again vaguely.

Later means later by **when the meeting started**, not by where the turn
sits in a transcript. Two meetings on the same day are ordered by their
start times; a person who commits twice inside one meeting is making one
commitment, and the later turn is the one that counts.

On this window, 81% of the rows carry a due date that differs between the
person's first statement and their last, and the register discards more
than four commitments for every one it keeps.

A commitment made once and never repeated is live. It does not need
restating to count.

## What to produce

One file in your workspace: **`commitment_revisions.json`**, with exactly
these fields:

- `meetings_read` — how many standing meetings you opened: every one inside
  the window, whatever was said in it.
- `turns_read` — how many turns those meetings contained.
- `distinct_owners` — how many different people hold a live commitment.
- `superseded_count` — how many commitments you found that a later one
  replaced, across the whole register. This is the sum of the `superseded`
  figures below and nothing more.
- `live` — **one entry per live commitment**, sorted by `meeting` then
  `owner`, each with:
  - `owner` — the person's full name
  - `meeting` — the standing meeting's title, exactly as the record gives it
  - `due` — the date it is due, as `YYYY-MM-DD`
  - `first_due` — the date this person **first** committed to in this
    standing meeting, as `YYYY-MM-DD`: the date their earliest qualifying
    statement in the series resolved to, **against the meeting it was said
    in**. Somebody who said "EOD" in January and "EOD" in June named two
    different dates, and this is the January one. Where they committed only
    once, it is the same date as `due`.
  - `superseded` — how many **earlier** commitments this person made in
    this standing meeting that this one replaced. A commitment made once
    and never revised is `0`.
    **The unit is one commitment per meeting.** A person who committed
    twice inside a single meeting made one commitment, as above, so it can
    be discarded once and not twice — count the meetings of this series in
    which they committed, not the turns, and subtract the one that is still
    live.
  - `meeting_id` — the meeting in which they last committed
  - `said_at` — the ISO-8601 start of that meeting

Two entries in `live` for the same person and the same standing meeting is
always wrong: only their latest commitment in that series is live.

## A warning about completeness

The register is only right if you have read every standing meeting in the
window. A commitment you never saw is a missing row; a commitment whose
later replacement you never saw is a **wrong** row, reported as live when
the firm has moved on — and it will be wrong in the date, which is the field
that cannot be recovered from anywhere else. There is no field anywhere that
lists commitments and no summary that collects them: the only way to know
what was said is to read what was said.

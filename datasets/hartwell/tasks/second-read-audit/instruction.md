# Supervision review: the second reads nobody gave

You are **Grace Adeyemi**, senior paralegal at Hartwell & Marsh LLP, and
Eleanor has handed you the least popular job of the quarter. The firm's
one real quality control before a document leaves the building is that
somebody else reads it: you ask a colleague privately, they come back to
you with their read, the draft goes out. Twice this year work has gone out
that nobody else had actually read, and both times the person who asked
swears they got an answer.

Eleanor wants the list. Not an impression — the requests themselves, and
which of them never drew a real second read inside the firm's standard.

Everything is in the firm's systems — Gmail, Slack, iManage, and Clio.
This audit is intentionally seatless: those tools expose the firm-wide
agent-facing record, not a single lawyer's mailbox or application seat.
The asking happens where people actually ask each other: one to one, in
Slack direct messages. Chat search does not reach into those, so there is
no shortcut here — the conversations have to be opened.

Save **`second-read.json`** in your workspace:

```json
{
  "requests_reviewed": <how many second-read requests were made, all conversations>,
  "conversations_reviewed": <how many one-to-one conversations you went through>,
  "unanswered_request_ts": ["<Slack ts of the request>", "..."],
  "unanswered_requests": [
    {
      "ts": "<Slack ts of the request>",
      "date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked>",
      "asked_of": "<who was asked>"
    }
  ],
  "answered_same_day": <how many requests drew a real read the same day>,
  "answered_next_working_day": <how many first drew a real read after the request day but by the deadline>,
  "unanswered_by_deadline": <how many drew no real read by the deadline>,
  "came_back_later": ["<Slack ts of each request whose read first landed after the request day but still inside the standard>"],
  "unanswered_askers": ["<each person whose request missed the deadline>"],
  "response_audit": [
    {
      "request_ts": "<Slack ts of the request>",
      "request_date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked>",
      "asked_of": "<who was asked>",
      "first_response_surface": "<slack, gmail, or none>",
      "first_response_id": "<Slack ts or Gmail message id; empty only for none>",
      "first_response_at": "<ISO-8601 timestamp; empty only for none>",
      "outcome": "<same_day, next_working_day, or unanswered>"
    }
  ]
}
```

The firm asks for a second read in one standing form of words: *mind
taking a quick look at my draft before it goes out?* Every instance of
that request, in every one-to-one conversation, is in scope. Review the
March through June 2026 period.

## What counts as the read

A request is **answered** only when the person who was asked comes back to
the asker with the **read itself** — their verdict on the draft. That means
one of:

- a later message from them, in that same one-to-one conversation, that
  delivers the read (an approval to send, edits or a redline, a sign-off);
  or
- a directed email from them to the asker delivering the read (its subject
  is marked as the draft read).

A message that only **acknowledges** the request and defers — *"got it,
I'll get to it tonight," "swamped, give me an hour," "it's in my queue"* —
is **not** the read. The read is the later message that actually delivers
the verdict. Likewise, the two of them being active elsewhere, the asker
writing again, ordinary chatter, and somebody else answering are all not
the read.

Use the chronologically **first real read** after the request, across both
surfaces (chat and mail). If the reviewer first acknowledges and then
delivers the read, it is the delivery that counts, not the acknowledgement.

## Which request a read answers

The same person sometimes **re-sends** the request before any read has come
back. A read answers the **most recent** request from that asker to that
reviewer that precedes it. So if the reviewer only comes back after the
re-send, the re-sent instance is answered and the original — which drew
only an acknowledgement, or nothing — is **unanswered**.

## Timing: Pacific working days

The firm works **Monday through Friday**, and treats U.S. federal holidays
as non-working days. Inside this review window that means **Memorial Day
(Monday, May 25, 2026)** and **Juneteenth (Friday, June 19, 2026)**.

Slack and Gmail serve timestamps in **machine time**; the firm's day
boundaries are **Pacific**. Convert each instant to Pacific before taking
its calendar date. A read at, say, 5:10 p.m. Pacific is still the **same
day** even though its UTC date is already the next one; a read at 12:10
a.m. Pacific is the **next** day.

For each request, compute the Pacific date it was asked and the Pacific
date of its first real read, then:

- **`same_day`** — the read landed the same Pacific date it was asked.
- **`next_working_day`** — the read first landed after the request date but
  no later than the **end of the next working day**, where the next working
  day is the next Monday-through-Friday day that is not a federal holiday.
  A Friday request read the following Monday is timely; a request the day
  before a holiday, read the first working day after it, is timely; a
  weekend or holiday read that precedes a still-open deadline is timely.
- **`unanswered`** — no real read landed by that deadline. If a real read
  did land but only **after** the deadline, record its true surface, id,
  and time, but classify the request `unanswered`.

Use `none` and empty response fields only when no real read ever landed.

## Reconciliation

`unanswered_request_ts` lists the request's own Slack `ts` for every request
that drew no real read inside its window. `came_back_later` lists the request
`ts` for every request first read after the request date but inside the
standard. `unanswered_askers` lists each person whose request missed the
deadline.

You are handing this to Eleanor as the complete list. A request assigned the
wrong outcome or omitted from the schedule makes the review incomplete and
must remain visible as an exception to certification.

`response_audit` is the retained review schedule and must contain all 75
requests, not only the exceptions. The three aggregate outcomes and each
exception list must reconcile exactly with those rows.

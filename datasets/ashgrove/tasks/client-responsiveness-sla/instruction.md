# Client responsiveness review

You are the client-service lead at **Ashgrove Reid LLP**. The managing
partner wants to know how quickly the firm answers its clients, and
which client messages are still sitting unanswered.

Systems available through tools: **gmail** (firm-wide mail), **clio**,
**slack**, **calendar**, **imanage**.

## What to produce

One file: **`sla_report.json`**, with exactly these fields:

- `threads_reviewed` — how many mail threads the firm holds in total.
- `threads_with_client_inbound` — how many of those carry at least one
  message from a client.
- `inbound_total` — messages from clients, across all threads.
- `unanswered_total` — client messages never answered.
- `firm_median_reply_hours` — median reply time across every answered
  client message, 2 dp.
- `slowest_thread` — the `thread_id` containing the single longest wait.
  Break a tie by taking the lower `thread_id`.
- `threads` — **one entry per thread that carries client mail**, sorted by
  `thread_id`, each with:
  - `thread_id` — the thread's id, as the mail surface shows it
  - `client` — the name of the client who wrote the **first** client
    message in that thread
  - `messages` — how many messages the thread holds in total, from
    everyone
  - `inbound` — how many of them came from clients
  - `unanswered` — how many client messages in it were never answered
  - `first_reply_hours` — the reply time of the **earliest** answered
    client message in the thread, 2 dp; `0.0` if none was answered
  - `longest_reply_hours` — the longest reply time in the thread, 2 dp;
    `0.0` if none was answered

## Who counts as a client

Not everyone outside the firm is a client. The directory records what
each outside contact is to Ashgrove, and only the client contacts belong
in this report — a peer reviewer examining the firm's own work is an
outside correspondent, not a client, and their messages are neither
inbound nor unanswered here.

Anyone outside the firm still counts as "not the firm" when deciding
whether a message was answered: a reply must come from someone inside
Ashgrove.

## How the firm measures a reply

A client message is **answered** when someone inside the firm writes
into the **same thread** after it. The reply time is the gap between the
client's message and that first firm message, in hours.

Two things follow, and both matter:

- When a client writes several times in a row, each of those messages is
  its own inbound, and the firm's next message answers **all** of them —
  each with its own reply time measured from its own timestamp.
- A client message with no later firm message in that thread is
  unanswered, and contributes to no median.

A thread with no answered client message has `first_reply_hours` and
`longest_reply_hours` of `0.0`.

Threads with no client mail at all — the firm talking to itself — are
counted in `threads_reviewed` and appear nowhere else.

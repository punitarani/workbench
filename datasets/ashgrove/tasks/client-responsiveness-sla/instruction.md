# Client responsiveness review

You are the client-service lead at **Ashgrove Reid LLP**. The managing
partner wants to know how quickly the firm answers its clients, and
which client messages are still sitting unanswered.

Systems available through tools: **gmail** (firm-wide mail), **clio**,
**slack**, **calendar**, **imanage**.

## What to produce

One file: **`sla_report.json`**, with exactly these fields:

- `clients` — how many client contacts wrote to the firm.
- `inbound_total` — messages from clients, across all threads.
- `unanswered_total` — client messages never answered.
- `firm_median_reply_hours` — median first-reply time across every
  answered client message, 2 dp.
- `slowest_client` — the client whose single longest wait was longest.
- `client_rows` — one entry per client, sorted by name: `client`,
  `inbound`, `answered`, `unanswered_message_ids` (sorted),
  `median_reply_hours` (2 dp), `longest_reply_hours` (2 dp).

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

A client with no answered messages has a median and longest of `0.0`.

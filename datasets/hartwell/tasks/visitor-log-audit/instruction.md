# Chain of custody: the visitor log returned after its deadline

You are **Omar Haddad**, records clerk at Hartwell & Marsh LLP. The reception
sign-in sheet is a firm record, but yesterday's page regularly travels upstairs
for conflicts and billing work. The annual records review found that the old
log treated an eventual return as timely even when custody had already broken,
and — worse — counted a colleague's *"still have it, I'll bring it down"* as if
the sheet were already back. Anita needs the audit rebuilt from the record.

Save **`visitor-log.json`** in your workspace with exactly this structure:

```json
{
  "requests_reviewed": <all requests across all one-to-one conversations>,
  "conversations_reviewed": <all one-to-one conversations reviewed>,
  "same_day_breach_ts": ["<Slack ts of each request not returned that day>"],
  "same_day_breaches": [
    {
      "ts": "<Slack ts of the request>",
      "date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked for the sheet>",
      "asked_of": "<who was asked>",
      "resolution": "<next_working_day or unresolved>"
    }
  ],
  "returned_same_day": <requests returned by the end of the day asked>,
  "returned_next_working_day": <breaches returned by the follow-up deadline>,
  "unresolved_by_followup": <breaches not returned by the follow-up deadline>,
  "returned_next_working_day_ts": ["<breach request ts later returned the next working day>"],
  "unresolved_ts": ["<breach request ts not returned by the end of the next working day>"],
  "custody_audit": [
    {
      "request_ts": "<Slack ts of the request>",
      "request_date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked for the sheet>",
      "asked_of": "<who was asked>",
      "first_return_surface": "<slack, gmail, or none>",
      "first_return_id": "<source-native Slack ts or Gmail message id, or empty>",
      "first_return_at": "<ISO timestamp with offset, or empty>",
      "outcome": "<same_day, next_working_day, or unresolved>"
    }
  ]
}
```

The standing request is exactly *do you still have the sign-in sheet from
yesterday?* Every instance in every Slack direct-message conversation from
March through June is in scope. Slack search does not expose DMs, so enumerate
and open every one-to-one lane. This audit is intentionally seatless: the tools
expose the firm's audit corpus rather than one employee's mailbox or Slack seat.

## What counts as the return

Custody is timely only when the sheet is physically back at the front desk by
the **end of the day it was asked**, and the person asked is the one who has to
bring it back — confirmation that yesterday's page has returned. That means one
of:

- a later message from them, in that same DM lane, saying the sheet is back at
  reception (back at the reception desk, back on the front desk, back in the
  reception binder, back on the sign-in clipboard, back downstairs at reception,
  returned to the front desk, or back on the desk out front); or
- an email from them, directed to the asker, whose subject marks the sheet as
  returned (*Sign-in sheet returned*).

A message that only **acknowledges** the request and defers — *"still have it
up here, I'll run it down later," "it's on my desk for the conflicts check,"
"haven't sent it down yet"* — is **not** the return. The return is the later
message that actually confirms the sheet is back. The response must occur
**after the request**. The asker writing again, either person speaking
elsewhere, ordinary chatter, and a third party answering are all not the return.

Use the chronologically **first real return** after the request, across both
surfaces (chat and mail). If the holder first acknowledges and then brings the
sheet back, it is the return that counts, not the acknowledgement.

## Which request a return answers

The same person sometimes **re-sends** the request before the sheet has come
back. A return closes the **most recent** request from that asker to that
holder that precedes it. So if the holder only brings the sheet back after the
re-send, the re-sent instance is closed and the original — which drew only an
acknowledgement, or nothing — is **unresolved**.

## Timing: Pacific working days and the custody deadline

The firm works **Monday through Friday**, and treats U.S. federal holidays as
non-working days. Inside this review window that means **Memorial Day (Monday,
May 25, 2026)** and **Juneteenth (Friday, June 19, 2026)**.

Slack and Gmail serve timestamps in **machine time**; the firm's day boundaries
are **Pacific**. Convert each instant to Pacific before taking its calendar
date. A return at, say, 5:40 p.m. Pacific is still the **same day** even though
its UTC date is already the next one; a return at 12:10 a.m. Pacific is the
**next** day.

For each request, compute the Pacific date it was asked and the Pacific date of
its first real return, then:

- **`same_day`** — the sheet came back the same Pacific date it was asked.
- **`next_working_day`** — the sheet first came back after the request date but
  no later than the **end of the next working day**, where the next working day
  is the next Monday-through-Friday day that is not a federal holiday. A Friday
  request returned the following Monday is timely; a request the working day
  before a holiday, returned the first working day after it, is timely.
- **`unresolved`** — no real return landed by that deadline, **even if someone
  eventually replies later**. If a real return did land but only **after** the
  deadline, record its true surface, id, and time, but classify the request
  `unresolved`.

Use `none` and empty response fields only when no real return ever landed (for
example, a request orphaned by a re-send).

## Reconciliation

Every request without a same-day return is a breach and belongs in both
`same_day_breach_ts` and `same_day_breaches`, classified `next_working_day` or
`unresolved` by the rule above. Repeat the same partition in the two scalar
counts, `returned_next_working_day_ts`, and `unresolved_ts`.

`custody_audit` must contain one row for every request, not only the breaches.
For each row, report the earliest qualifying return across both surfaces. Keep
the actual source, source-native identifier, and time even when that first
return missed the follow-up deadline; use `none` and empty strings only when no
qualifying return exists. The ledger, counts, breach records, and timestamp
partitions must reconcile exactly.

The cross-surface direction and timing rules matter. Some returns arrived by
email rather than chat, some same-day returns land in the evening whose UTC
date has already rolled over, weekend and holiday requests cross to the next
working day, and one request was orphaned by a re-send while another was not
returned until after its next-working-day window. Certify the exact population,
breach records, and partitions without adding commentary or private evidence
fields to the JSON.

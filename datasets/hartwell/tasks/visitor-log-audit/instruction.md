# Chain of custody: the visitor log returned after its deadline

You are **Omar Haddad**, records clerk at Hartwell & Marsh LLP. The reception
sign-in sheet is a firm record, but yesterday's page regularly travels upstairs
for conflicts and billing work. The annual records review found that the old
log treated an eventual return as timely even when custody had already broken.
Anita needs the audit rebuilt from the record.

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

Custody is timely only when the person asked comes back to the asker by the
**end of the day it was asked**. A qualifying return is either a later message
from the person asked in that same DM lane or a later email from that person
directed to the asker. The response must occur after the request. The asker
writing again, either person speaking elsewhere, or a third party answering
does not close custody.

Every request without that same-day return is a breach and belongs in both
`same_day_breach_ts` and `same_day_breaches`. Classify it
`next_working_day` only if a qualifying return arrives after the request date
but no later than the end of the immediately next working day; the firm works
Monday through Friday, so a weekend return after a Friday request is timely for
this follow-up classification because Monday is the deadline. Classify it
`unresolved` if no qualifying return arrives by that deadline, even if someone
eventually replies later. Repeat the same partition in the two scalar counts,
`returned_next_working_day_ts`, and `unresolved_ts`.

`custody_audit` must contain one row for every request, not only the breaches.
For each row, report the earliest qualifying return across both surfaces. Keep
the actual source, source-native identifier, and time even when that first
return missed the follow-up deadline; use `none` and empty strings only when no
qualifying return exists. The ledger, counts, breach records, and timestamp
partitions must reconcile exactly.

The cross-surface direction and timing rules matter. One next-working-day
return arrived by email before the Slack reply, weekend requests cross to
Monday, and two requests were not returned until after their next-working-day
window. Certify the exact population, breach records, and partitions without
adding commentary or private evidence fields to the JSON.

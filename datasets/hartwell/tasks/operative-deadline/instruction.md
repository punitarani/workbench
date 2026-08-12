# Docket check: when is the Arroyo motion hearing?

You are **Sofia Ramirez**, associate at Hartwell & Marsh LLP, covering
docketing while Grace is out. Samuel wants absolute certainty about the
motion hearing in *Arroyo Construction v. Fruitvale Partners* — it has
been continued more than once, and he does not want anyone preparing
against a stale notice. Establish the operative hearing date and the
full history of dates it replaced.

The firm runs on Gmail, Slack, iManage, and Clio; the answer is somewhere
in them.
This audit is intentionally seatless: those tools expose the firm-wide
agent-facing record, not a single lawyer's mailbox or application seat.

Save **`deadline.json`** in your workspace:

```json
{
  "operative_date": "<YYYY-MM-DD of the hearing as it currently stands>",
  "operative_time": "<HH:MM local time of the hearing>",
  "correction_ts": "<Slack ts of the message that establishes the operative date>",
  "superseded_dates": ["<YYYY-MM-DD>", "..."],
  "supersessions": [
    {
      "invalidated": "<YYYY-MM-DD superseded hearing date>",
      "by": "<Gmail message id or Slack ts of the notice or message that invalidated it>"
    }
  ],
  "stale_calendar_refs": ["<Gmail message id or Slack ts>", "..."],
  "notice_audit": [
    {
      "message_id": "<Gmail message id or Slack ts>",
      "surface": "gmail" | "slack",
      "cites_date": "<YYYY-MM-DD hearing date this message names>",
      "operative_when_sent": "<YYYY-MM-DD date operative the moment it was sent>",
      "classification": "current" | "stale" | "correction"
    }
  ]
}
```

`superseded_dates` lists every previously noticed hearing date in the
order they were set. `supersessions` names, for **each** superseded date,
the specific item that invalidated it — the Gmail message id of the
notice that moved the hearing off that date, or the Slack ts if the move
reached the firm some other way first.

**The firm dockets from the first reliable report, not the written
confirmation.** When the court tells us a setting is gone — a clerk's
call relayed into the file counts — that date is off the calendar from
the moment we are told, not from the day the paper arrives. The
instrument that invalidated a date is therefore the first reliable report
of the move, and anything written afterward that still treats the old
date as the setting was already wrong when it was sent, however
reasonable it looked at the time. Some of our own filings sit in that
gap. Do not stop at the court's written notices,
and do not assume the most recent internal mail is current: check
everything the firm wrote afterward, and cite (via `correction_ts`) the
message that makes your operative date the operative one.

Samuel also wants the contamination mapped, so nobody preps from a
message that was already wrong when it was sent: `stale_calendar_refs`
must list **every communication — email (by Gmail message id) or Slack
message (by ts) — that still cites a superseded date as this hearing's
setting after the item that superseded it**. A message that reports
the move, or that names the old date only to deny it, is a correction,
not a stale reference; a message citing a date while that date was still
operative is simply current. Cross-reference every mention of every
noticed date against the correction timeline before you call it clean,
and satisfy yourself that each one you list is setting *this* hearing.

`notice_audit` is the schedule that reasoning has to stand on, and it is
the deliverable Samuel will actually read. Give it a row for **every**
communication in the matter that names any hearing date — the three the
court noticed and the one that now stands — whether that mention turned
out to be fine or not. Identify the matter however the firm did: the
case name, the department, or the Clio matter number; the correction
never spells the caption. For each row give the message id, the surface
it lives on, the date it names, the date that was operative *at the
instant it was sent*, and the judgement: `current` when it named the
date then in force, `stale` when that date had already been superseded,
`correction` when the message is itself the instrument that moved the
hearing or names a date only to deny it. A message naming two hearing
dates earns a row for each — a notice that retires one date and sets
another is making two statements, and the audit records both. A
superseding instrument speaks from its own timestamp, so it reports the
date it sets rather than citing a stale one.

`stale_calendar_refs` must be exactly the message ids of the rows you
classified `stale`; if the two disagree, the audit is not finished. Samuel is going to circulate this list as the
definitive one, so it has to be exactly right: one message listed that
was current when sent, or one contaminated message left off, and the
list is worse than none.

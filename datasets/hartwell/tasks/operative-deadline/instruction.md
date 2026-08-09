# Docket check: when is the Arroyo motion hearing?

You are **Sofia Ramirez**, associate at Hartwell & Marsh LLP, covering
docketing while Grace is out. Samuel wants absolute certainty about the
motion hearing in *Arroyo Construction v. Fruitvale Partners* — it has
been continued more than once, and he does not want anyone preparing
against a stale notice. Establish the operative hearing date and the
full history of dates it replaced.

The firm runs on Gmail, Slack, iManage, and Clio; the answer is somewhere
in them.

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
  "stale_calendar_refs": ["<Gmail message id or Slack ts>", "..."]
}
```

`superseded_dates` lists every previously noticed hearing date in the
order they were set. `supersessions` names, for **each** superseded date,
the specific item that invalidated it — the Gmail message id of the
notice that moved the hearing off that date, or the Slack ts if the move
was never noticed in writing. Do not stop at the court's written notices,
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
operative is simply current. Other matters moved that season too — a
different case's hearing date is not this hearing's. Cross-reference
every mention of every noticed date against the correction timeline
before you call it clean. Samuel is going to circulate this list as the
definitive one, so it has to be exactly right: one message listed that
was current when sent, or one contaminated message left off, and the
list is worse than none.

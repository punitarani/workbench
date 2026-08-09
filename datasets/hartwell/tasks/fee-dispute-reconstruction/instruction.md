# Billing reconstruction: the Meridian April invoice dispute

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. The
May 2026 dispute over the Meridian BioLabs April invoice was resolved,
but the file needs a precise numeric record of what was actually disputed
— the client's challenge turned on time entered *after* the budget call
that re-scoped the data-room diligence, and the resolution capped exactly
that work.

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`dispute.json`** to the workspace root:

```json
{
  "cutoff_date": "<YYYY-MM-DD budget-call cutoff the parties agreed>",
  "total_minutes": <total minutes of the disputed diligence work>,
  "entry_count": <number of time entries that make it up>,
  "entries": [
    {
      "id": <Clio activity id of the disputed time entry>,
      "date": "<YYYY-MM-DD of the entry>",
      "minutes": <minutes of the entry>
    }
  ],
  "minutes_by_timekeeper": {"<timekeeper name>": <their disputed minutes>},
  "timekeepers": ["<everyone who logged that work>"],
  "challenged_by": "<who challenged the invoice>",
  "challenge_date": "<YYYY-MM-DD the client disputed the invoice>",
  "unsupported_entry_ids": [<Clio activity ids, see the support audit>]
}
```

The disputed work is every time entry on the Meridian diagnostics
acquisition matter dated **strictly after the budget-call cutoff** whose
narrative describes the data-room diligence (the entries whose notes
mention diligence or the data room). Establish the cutoff date from the
firm's record — the emails and the matter note describe the split but
never state the date — and beware of near misses on every side of the
join: diligence work on this matter began before the cutoff, an entry
landed on the cutoff day itself, other matters carried diligence and
data-room work that April, and post-cutoff Meridian entries describe the
expanded scope without the diligence wording. A sum over every diligence
entry, over the whole billing month, or over every matter is wrong.
`entries` must list the exact disputed Clio time entries — id, date, and
minutes each — and count minutes from the record, not from anyone's
summary; no email states the figures.

The resolution also ordered a **support audit** over the disputed
window. For every time entry on the Meridian matter dated after the
budget-call cutoff through the end of April, the file must show
same-day client-visible activity: at least one email (subject or body
text) or Slack message (any channel or any DM), sent on the entry's
date, that names the engagement — the client (Meridian), the deal (the
diagnostics acquisition), or the matter number (00001). Vague
references do not count: a data room, a tranche, a privilege screen, or
a diligence call could belong to any matter (the Solstice closing
staged a seller data room the same month), so a message supports an
entry only when it names the engagement in one of those three forms.
`unsupported_entry_ids` must list the Clio activity id of every window
entry — diligence-worded or not — whose date has no such message
anywhere in the record. Expect to check every surface before calling a
day silent: on some days the only qualifying message sits in a DM that
channel search never returns, and on others it never uses the client's
name. Listing an entry whose day has support counts against you exactly
like missing a true orphan.

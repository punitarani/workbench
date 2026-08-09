# Billing reconstruction: the Meridian April invoice dispute

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. The
May 2026 dispute over the Meridian BioLabs April invoice was resolved,
but the file needs a precise numeric record of what was actually disputed
— the client's challenge turned on time entered *after* the April 3
budget call, and the resolution capped exactly that work.

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
  "timekeepers": ["<everyone who logged that work>"],
  "challenged_by": "<who challenged the invoice>",
  "challenge_date": "<YYYY-MM-DD the client disputed the invoice>"
}
```

The disputed work is every time entry on the Meridian diagnostics
acquisition matter dated **after the budget-call cutoff** whose narrative
describes the data-room diligence (the entries whose notes mention
diligence or the data room). Establish the cutoff date from the firm's
record — the emails and the matter note describe the split but never
state the date — and beware that diligence work on this matter began
before the cutoff: a sum over every diligence entry, or over the whole
billing month, is wrong. Count minutes from the record, not from anyone's
summary; no email states the figures.

# Docket check: when is the Arroyo motion hearing?

You are **Sofia Ramirez**, associate at Hartwell & Marsh LLP, covering
docketing while Grace is out. Samuel wants absolute certainty about the
motion hearing in *Arroyo Construction v. Fruitvale Partners* — it has
been continued more than once, and he does not want anyone preparing
against a stale notice. Establish the operative hearing date and the
full history of dates it replaced.

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`deadline.json`** to the workspace root:

```json
{
  "operative_date": "<YYYY-MM-DD of the hearing as it currently stands>",
  "operative_time": "<HH:MM local time of the hearing>",
  "correction_ts": "<Slack ts of the message that establishes the operative date>",
  "superseded_dates": ["<YYYY-MM-DD>", "..."]
}
```

`superseded_dates` lists every previously noticed hearing date in the
order they were set. Do not stop at the court's written notices: verify
against everything the firm recorded afterward, and cite (via
`correction_ts`) the record that makes your operative date the operative
one.

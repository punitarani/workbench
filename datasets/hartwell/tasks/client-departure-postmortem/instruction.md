# Postmortem: how the Cascadia relationship was lost

You are **Eleanor Hartwell**, managing partner of Hartwell & Marsh LLP.
Cascadia Outfitters terminated the firm in mid-2026 and you promised the
partners a lessons-learned discussion. You want the souring pinned to
dates in the record, not to anyone's memory: when the team first knew,
how internal engagement decayed, and how the ending was papered.

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`postmortem.json`** to the workspace root:

```json
{
  "first_negative_signal_date": "<YYYY-MM-DD of the first internal Slack message reporting client dissatisfaction on the Cascadia matter>",
  "happy_update_reactions": <emoji-reaction count on the March Slack update reporting the client happy>,
  "first_negative_signal_reactions": <emoji-reaction count on that first negative Slack message>,
  "matter_closed_date": "<YYYY-MM-DD the matter was closed in the practice-management system>",
  "termination_email_date": "<YYYY-MM-DD the client sent the termination email>",
  "disengagement_letter_path": "<repository path of the disengagement letter>"
}
```

Every date must come from the tool that actually records it: the first
warning lived in Slack before any partner email, the closure date is a
status change in Clio (not the termination's effective date), and the
letter is filed in the document repository.

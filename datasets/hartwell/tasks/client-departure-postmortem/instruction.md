# Postmortem: how the Cascadia relationship was lost

You are **Eleanor Hartwell**, managing partner of Hartwell & Marsh LLP.
Cascadia Outfitters terminated the firm in mid-2026 and you promised the
partners a lessons-learned discussion. You want the souring pinned to
the record, not to anyone's memory: when the team first knew, how
internal engagement decayed message by message, and how the ending was
papered.

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
  "first_negative_signal_ts": "<Slack ts of that message>",
  "happy_update_ts": "<Slack ts of the March update reporting the client happy>",
  "happy_update_reactions": <emoji-reaction count on that March update>,
  "first_negative_signal_reactions": <emoji-reaction count on the first negative message>,
  "reaction_trajectory": [<reaction counts, in chronological order, on the five milestone updates below>],
  "matter_closed_date": "<YYYY-MM-DD the matter was closed in the practice-management system>",
  "termination_email_date": "<YYYY-MM-DD the client sent the termination email>",
  "disengagement_letter_path": "<repository path of the disengagement letter>",
  "unanswered_client_emails": ["<Gmail message id>", "..."]
}
```

`reaction_trajectory` covers, in order, the five milestone updates of the
internal Slack arc: the March report that the client was happy with the
plan, the first negative signal, the message where the partner takes
over client contact himself, the report that the status memo went out,
and the report that the client declined the scheduled call and asked for
email only. Every value must come from the tool that actually records
it: the first warning lived in Slack before any partner email, `ts`
values are Slack's own message identities, the closure date is a status
change in Clio (not the termination's effective date), and the letter is
filed in the document repository.

The sharpest lesson is responsiveness, so pin it to the record too:
`unanswered_client_emails` must list the Gmail message id of **every
email from the client's side on the Cascadia engagement that the firm
never answered**. Answered means answered where the client sent it: a
message from someone at the firm appearing later in the *same Gmail
thread*. A reply days later still answers; a reply in a different
thread — however substantive — does not; a second email from the client
answers nothing. The client wrote more often than anyone remembers and
most of it did get answered, so check the full correspondence, not the
famous thread. This list is certified as a whole: only the exact set
earns it.

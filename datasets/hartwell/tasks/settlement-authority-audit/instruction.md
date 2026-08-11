# Settlement-authority audit: Project Marigold

You are **Samuel Marsh**, litigation partner at Hartwell & Marsh LLP. The
malpractice carrier has selected the Goldleaf franchise litigation for a
settlement-authority review. The client—not counsel—controls settlement, and
the audit must show whether each concrete proposal the firm sent to opposing
counsel was inside the authority documented at the moment it went out.

The file uses a negotiation code name. Resolve that name, the exact Clio matter
number, the client decision-maker, and opposing counsel from the firm record
before deciding what correspondence belongs to the matter. Review the July 1
through September 18, 2026 Pacific-time period. Gmail, Slack, iManage, and
Clio expose the firm-wide record; this task is intentionally seatless.

Save **`authority.json`** with exactly this public structure:

```json
{
  "matter_number": "<exact Clio display number>",
  "negotiation_alias": "<the code name used in negotiation traffic>",
  "client_decision_maker": "<full name>",
  "opposing_counsel": ["<full name>", "..."],
  "proposal_count": <number of outbound proposals reviewed>,
  "authorized_count": <number compliant with authority>,
  "breach_count": <number not compliant>,
  "breach_message_ids": ["<Gmail message id>", "..."],
  "authority_timeline": [
    {
      "effective_at": "<ISO-8601 timestamp with offset>",
      "surface": "gmail or slack",
      "source_ids": ["<Gmail message id or Slack ts>", "..."],
      "status": "grant or hold",
      "amount_cents": <integer; 0 for a hold>,
      "amount_rule": "minimum, exact, or none",
      "economic_basis": "exclusive, inclusive, net_plus_fees, or none",
      "required_terms": ["<normalized term>", "..."],
      "prohibited_terms": ["<normalized term>", "..."],
      "expires_at": "<ISO-8601 timestamp with offset, empty for none>"
    }
  ],
  "proposal_audit": [
    {
      "message_id": "<Gmail message id>",
      "sent_at": "<ISO-8601 timestamp with offset>",
      "sender": "<full name>",
      "amount_cents": <integer>,
      "economic_basis": "exclusive, inclusive, or net_plus_fees",
      "terms": ["<normalized term>", "..."],
      "authority_source_ids": ["<source ids for the authority state applied>", "..."],
      "disposition": "authorized, amount_outside_authority, economic_terms_mismatch, authority_revoked, authority_expired, or nonmonetary_terms_mismatch"
    }
  ]
}
```

An outbound proposal is a Gmail message from Hartwell & Marsh to the opposing
counsel identified in the matter record that communicates a concrete dollar
proposal for this dispute. Do not count the opponent's offers, internal drafts,
status mail, or client instructions. Review every qualifying outbound message,
including repeated numbers.

Build the authority state chronologically. A later client instruction replaces
an earlier one. A hold or revocation takes effect immediately. A proposal sent
after a stated expiry is outside authority; a proposal at the exact expiry
moment remains inside it. The client sometimes gives authority by telephone;
a contemporaneous partner DM is accepted as documented authority for this
audit, and a clarification in that same DM is part of the source record. Do
not treat ordinary internal discussion as client authority.

Test each proposal against all documented dimensions: the amount rule, whether
fees and costs are inclusive, exclusive, or separately payable, required
non-monetary terms, prohibited terms, and the time window. Use these normalized
term labels when they apply: `mutual_release`, `general_release`,
`release_unknown_claims`, `mutual_non_disparagement`, `confidentiality`,
`no_confidentiality`, `inventory_transition_60_days`, and
`payment_within_10_days`. Sort terms and names alphabetically. Keep source ids
in chronological order, and order both audit arrays chronologically.

For a noncompliant proposal, apply one disposition using this priority:
`authority_revoked`, then `authority_expired`, then
`amount_outside_authority`, then `economic_terms_mismatch`, then
`nonmonetary_terms_mismatch`. The counts and breach list must reconcile to the
proposal schedule exactly. This is the carrier's retained workpaper; a summary
without the underlying chronology is not a certification.

# Playbook drift audit: vendor NDAs

You are **Diane Okonkwo**, of counsel at Hartwell & Marsh LLP. It is late
June 2026 and a vendor-NDA playbook review is going on next quarter's
calendar. Before that meeting you need the drift documented precisely —
and completely. The review will certify every vendor NDA on file, so the
audit must say, for each one, whether its history conforms to the
written playbook or departs from it, and for the departures, exactly
which document, which version, and which clause.

Work from the firm's systems: Gmail, Slack, Clio, and iManage, where the
playbook and the NDAs are filed with their full version histories.
This audit is intentionally seatless: those tools expose the firm-wide
agent-facing record, not a single lawyer's mailbox or application seat.
All `YYYY-MM-DD` values use the firm's Pacific calendar
(`America/Los_Angeles`). iManage exposes save timestamps in UTC, so convert
those timestamps to Pacific time before assigning a version to a calendar day.

Save **`drift.json`** in your workspace:

```json
{
  "playbook_path": "<iManage path of the vendor NDA playbook>",
  "ndas": {
    "<iManage path of a vendor NDA>": "conforms" | "deviates"
  },
  "silent_versions": ["<iManage version id, e.g. LEGAL!7.2>", "..."],
  "term": {
    "playbook_standard": "<what the playbook requires for the confidentiality term>",
    "practice": "<what the firm actually agreed to>",
    "document_path": "<iManage path of the vendor NDA whose redline diverged>",
    "version": <version number that introduced the divergence>,
    "date": "<YYYY-MM-DD of that version>"
  },
  "residuals": {
    "playbook_standard": "<the playbook's position on residual-knowledge clauses>",
    "practice": "<what the firm actually agreed to>",
    "document_path": "<iManage path of the vendor NDA whose redline diverged>",
    "version": <version number that introduced the divergence>,
    "date": "<YYYY-MM-DD of that version>"
  },
  "versions_reviewed": <number of post-v1 NDA versions reviewed>,
  "substantive_versions": <number with an operative-clause change>,
  "notices_only_versions": <number changing notices only>,
  "unchanged_versions": <number with no text change>,
  "covered_substantive_versions": <substantive versions with same-day email>,
  "silent_substantive_versions": <substantive versions without same-day email>,
  "covering_email_count": <total exact emails cited in the audit>,
  "version_audit": [
    {
      "version_id": "LEGAL!<document number>.<version>",
      "document_path": "<exact iManage path>",
      "date": "<YYYY-MM-DD save date>",
      "change_class": "<substantive, notices_only, or unchanged>",
      "email_ids": ["<exact same-day covering Gmail message id>", "..."]
    }
  ]
}
```

`ndas` is the certification: one entry for **every** vendor NDA in the
repository, keyed by its exact iManage path, valued `"conforms"` when
every version of that NDA holds the playbook's standard positions and
`"deviates"` when any version departs from them. You are signing this
certification as a whole — a missing NDA, an invented one, or a single
wrong call makes the whole thing unusable at the review — so do not
sample, and do not trust the email trail to tell you which files moved:
the mail discusses some departures and never mentions others.

For the two clause blocks, be precise: cite the specific NDA document
and the specific version whose content first departed from the
playbook's standard on each clause, not the emails that talk about it.
The playbook states the standards; the divergence lives in the redline
history.

`silent_versions` is the review's process finding: every vendor-NDA
version (across all nine files, version 2 and later) that
**substantively changed the agreement with no covering email that
day**. A version is substantive when its text changes an operative
clause — one stating a party's rights or obligations (term, residuals,
equitable relief, governing law, return of materials, non-solicitation,
and the like) — as opposed to versions that only touch notices,
addresses, signature blocks, exhibits, or nothing at all. A covering
email is any email sent the same calendar day that names that vendor or
carries that NDA file as an attachment; email is the firm's transmittal
record. List each such version by its iManage version
id (`LEGAL!<number>.<version>`). This finding is exact as well — a
missed version or a padded one and the process point falls apart. The
mail discusses some of these files and never mentions others, so only
the version walk plus a per-day mail check answers it.

The review committee needs the certification schedule behind those four
exceptions. `version_audit` must contain every version 2 and later of all nine
vendor NDAs. Classify a row `unchanged` when its text is byte-identical to the
prior version, `notices_only` when removing the Notices section makes the two
versions identical, and `substantive` otherwise. Cite every email that meets
the covering rule above and nothing else, identified by its exact Gmail
message ID.
The seven aggregate fields must reconcile with the schedule, and
`silent_versions` must be exactly the `version_id` partition of substantive
rows with an empty `email_ids` list.

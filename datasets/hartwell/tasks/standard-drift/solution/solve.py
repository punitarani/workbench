"""Reference oracle for standard-drift; emits the certified deliverable on stdout."""

import json
import os
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def iso(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()


def versions(path_like):
    found = rows(
        "imanage.db",
        "SELECT d.path, v.version, v.author, v.content, v.time FROM versions v "
        "JOIN documents d ON d.document_id = v.document_id "
        "WHERE d.path LIKE ? ORDER BY d.path, v.version",
        path_like,
    )
    if not found:
        sys.exit(f"no document matching {path_like!r} in the repository")
    return found


playbook = versions("%vendor-nda-playbook%")
playbook_path, _, _, playbook_head, _ = playbook[-1]
if "three (3) years" not in playbook_head:
    sys.exit("playbook term standard (three-year cap) not found in the record")
if "Reject any residual-knowledge clause" not in playbook_head:
    sys.exit("playbook residuals standard not found in the record")

# Walk every vendor NDA on file, not just the ones the mail discusses.
nda_paths = sorted({path for path, *_ in versions("%/firm/vendor-ndas/%")})
if len(nda_paths) != 9:
    sys.exit(f"expected nine vendor NDAs on file, found {len(nda_paths)}")


def first_with(path, needle):
    """First version of ``path`` whose content contains ``needle``."""
    for _doc_path, version, _author, content, time in versions(path):
        if needle in content:
            return version, time
    return None, None


term_hits = []
residual_hits = []
survey = {}
for path in nda_paths:
    history = versions(path)
    conforming = all(
        "three (3) years" in content and "Residual Knowledge" not in content
        for _, _, _, content, _ in history
    )
    survey[path] = "conforms" if conforming else "deviates"
    five_version, five_time = first_with(path, "five (5) years")
    if five_version is not None:
        earlier = [c for _, v, _, c, _ in history if v < five_version]
        term_hits.append((path, five_version, five_time, earlier))
    residual_version, residual_time = first_with(path, "Residual Knowledge")
    if residual_version is not None:
        if any(
            "Residual Knowledge" in c
            for _, v, _, c, _ in history
            if v < residual_version
        ):
            sys.exit(f"{path}: residuals divergence is not a clean boundary")
        residual_hits.append((path, residual_version, residual_time))

conforming_paths = [path for path in nda_paths if survey[path] == "conforms"]
if len(conforming_paths) != 7:
    sys.exit(f"expected exactly seven conforming NDAs, found {len(conforming_paths)}")

# Term drift: the NDA that started on three years and flipped to five.
flipped = [
    (path, version, time)
    for path, version, time, earlier in term_hits
    if earlier and all("three (3) years" in content for content in earlier)
]
if len(flipped) != 1:
    sys.exit(f"expected exactly one three-to-five term flip, found {len(flipped)}")
lex_path, lex_version, lex_time = flipped[0]

if len(residual_hits) != 1:
    sys.exit(
        f"expected exactly one NDA to gain a residuals clause, "
        f"found {len(residual_hits)}"
    )
iron_path, iron_version, iron_time = residual_hits[0]

# The residuals concession must be keyword-invisible outside the version
# content: no mail or chat names the clause for that vendor.
leaks = rows(
    "gmail.db",
    "SELECT COUNT(*) FROM messages WHERE subject LIKE '%Ironclad%' "
    "AND lower(body) LIKE '%residual%'",
)
chat_leaks = rows(
    "slack.db",
    "SELECT COUNT(*) FROM messages WHERE lower(body) LIKE '%residual%'",
)
if leaks[0][0] or chat_leaks[0][0]:
    sys.exit("the residuals flip leaked into keyword-searchable text")

# The covering emails corroborate that the divergent versions went out —
# and five of the nine NDAs never touch the mail record at all, so a
# mail-driven survey cannot be complete.
sent = rows(
    "gmail.db",
    "SELECT COUNT(*) FROM messages m JOIN attachments a "
    "ON a.message_id = m.message_id WHERE a.filename IN (?, ?)",
    "mutual-nda-lexipoint.md",
    "mutual-nda-ironclad.md",
)
if sent[0][0] < 2:
    sys.exit("covering emails for the divergent NDAs not found")
mailed = rows(
    "gmail.db",
    "SELECT COUNT(*) FROM messages WHERE lower(subject || ' ' || body) LIKE ?",
    "%trueline%",
)
if mailed[0][0]:
    sys.exit("a fabric NDA leaked into the mail record; the survey is cheap now")

# Silent substantive versions: diff every consecutive NDA version pair
# (notices-only edits are not substantive), then anti-join against the
# same-day mail record naming the vendor or carrying the file.
numbers = dict(rows("imanage.db", "SELECT path, document_number FROM documents"))
mail_texts = [
    (message_id, iso(time), (subject + " " + body + " " + filenames).lower())
    for message_id, subject, body, time, filenames in rows(
        "gmail.db",
        "SELECT m.message_id, m.subject, m.body, m.time, "
        "COALESCE((SELECT group_concat(a.filename, ' ') FROM attachments a "
        "WHERE a.message_id = m.message_id), '') FROM messages m",
    )
]


def strip_notices(content):
    sections = content.split("\n## ")
    kept = [sections[0]] + [s for s in sections[1:] if not s.startswith("Notices")]
    return "\n## ".join(kept)


silent_versions = []
covered = 0
nonsubstantive = 0
version_audit = []
for path in nda_paths:
    vendor = path.rsplit("/", 1)[-1].removeprefix("mutual-nda-").removesuffix(".md")
    history = versions(path)
    for (_, _, _, previous, _), (_, version, _, current, time) in zip(
        history, history[1:], strict=False
    ):
        day = iso(time)
        email_ids = sorted(
            message_id
            for message_id, mail_day, text in mail_texts
            if day == mail_day and vendor in text
        )
        if previous == current:
            change_class = "unchanged"
        elif strip_notices(previous) == strip_notices(current):
            change_class = "notices_only"
            nonsubstantive += 1
        else:
            change_class = "substantive"
            if email_ids:
                covered += 1
            else:
                silent_versions.append(f"LEGAL!{numbers[path]}.{version}")
        version_audit.append(
            {
                "version_id": f"LEGAL!{numbers[path]}.{version}",
                "document_path": path,
                "date": day,
                "change_class": change_class,
                "email_ids": email_ids,
            }
        )
if len(silent_versions) != 4:
    sys.exit(f"expected exactly four silent substantive versions: {silent_versions}")
if covered != 4:
    sys.exit(f"expected four covered substantive versions as noise, found {covered}")
if nonsubstantive != 1:
    sys.exit(
        "expected one real-but-nonsubstantive diff as near-miss noise, "
        f"found {nonsubstantive}"
    )

drift = {
    "playbook_path": playbook_path,
    "ndas": survey,
    "silent_versions": sorted(silent_versions),
    "versions_reviewed": len(version_audit),
    "substantive_versions": sum(
        item["change_class"] == "substantive" for item in version_audit
    ),
    "notices_only_versions": sum(
        item["change_class"] == "notices_only" for item in version_audit
    ),
    "unchanged_versions": sum(
        item["change_class"] == "unchanged" for item in version_audit
    ),
    "covered_substantive_versions": covered,
    "silent_substantive_versions": len(silent_versions),
    "covering_email_count": sum(len(item["email_ids"]) for item in version_audit),
    "version_audit": version_audit,
    "term": {
        "playbook_standard": (
            "Confidentiality obligations capped at three (3) years; longer "
            "terms need Managing Partner sign-off."
        ),
        "practice": (
            "Agreed to the vendor's five (5) year confidentiality term to "
            "keep the renewal on schedule."
        ),
        "document_path": lex_path,
        "version": lex_version,
        "date": iso(lex_time),
    },
    "residuals": {
        "playbook_standard": (
            "Reject any residual-knowledge clause outright; unaided-memory "
            "information stays confidential."
        ),
        "practice": (
            "Accepted the vendor's position: a Residual Knowledge clause "
            "was added to the signing draft."
        ),
        "document_path": iron_path,
        "version": iron_version,
        "date": iso(iron_time),
    },
}
json.dump(drift, sys.stdout, indent=2)
sys.stdout.write("\n")

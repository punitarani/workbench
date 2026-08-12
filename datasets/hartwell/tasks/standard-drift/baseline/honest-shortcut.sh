#!/bin/sh
# A stronger shortcut than naive.sh, which answers from the mail alone and
# so cannot produce a version schedule at all. This one does the whole
# mechanical walk -- opens every NDA history, diffs consecutive versions,
# classifies each change, and cites same-day covering mail -- and then
# looks for playbook rule 5 authority the obvious way: search Gmail for
# the vendor's name. That finds an approval only when one names the
# vendor, so the two sign-offs that cite the redline by iManage number and
# the one given in chat read as never authorized. It exists to measure
# whether the authority join adds difficulty over the diff.
exec python3 - << 'EOF'
import json
import os
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def iso(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()


def strip_notices(content):
    sections = content.split("\n## ")
    kept = [sections[0]] + [s for s in sections[1:] if not s.startswith("Notices")]
    return "\n## ".join(kept)


numbers = dict(rows("imanage.db", "SELECT path, document_number FROM documents"))
mail = [
    (message_id, iso(time), (subject + " " + body + " " + files).lower())
    for message_id, subject, body, time, files in rows(
        "gmail.db",
        "SELECT m.message_id, m.subject, m.body, m.time, "
        "COALESCE((SELECT group_concat(a.filename, ' ') FROM attachments a "
        "WHERE a.message_id = m.message_id), '') FROM messages m",
    )
]
histories = {}
for path, version, content, time in rows(
    "imanage.db",
    "SELECT d.path, v.version, v.content, v.time FROM versions v "
    "JOIN documents d ON d.document_id = v.document_id "
    "WHERE d.path LIKE '%/firm/vendor-ndas/%' ORDER BY d.path, v.version",
):
    histories.setdefault(path, []).append((version, content, time))

audit = []
silent = []
for path, history in sorted(histories.items()):
    vendor = path.rsplit("/", 1)[-1].removeprefix("mutual-nda-").removesuffix(".md")
    for (_, previous, _), (version, current, time) in zip(
        history, history[1:], strict=False
    ):
        day = iso(time)
        email_ids = sorted(m for m, sent, text in mail if sent == day and vendor in text)
        if previous == current:
            change_class = "unchanged"
        elif strip_notices(previous) == strip_notices(current):
            change_class = "notices_only"
        else:
            change_class = "substantive"
            if not email_ids:
                silent.append(f"LEGAL!{numbers[path]}.{version}")
        if change_class == "substantive":
            # The obvious authority search: the vendor's name in the mail.
            found = sorted(
                (sent, m)
                for m, sent, text in mail
                if vendor in text
                and any(w in text for w in ("approved", "approval", "signed off"))
                and sent < day
            )
            if found:
                sign_off, ref, signed = "present", found[-1][1], found[-1][0]
            else:
                sign_off, ref, signed = "absent", "", ""
        else:
            sign_off, ref, signed = "not_required", "", ""
        audit.append(
            {
                "version_id": f"LEGAL!{numbers[path]}.{version}",
                "document_path": path,
                "date": day,
                "change_class": change_class,
                "email_ids": email_ids,
                "sign_off": sign_off,
                "sign_off_ref": ref,
                "sign_off_date": signed,
            }
        )

counts = {k: sum(r["change_class"] == k for r in audit)
          for k in ("substantive", "notices_only", "unchanged")}
authority = {k: sum(r["sign_off"] == k for r in audit)
             for k in ("present", "absent", "after_the_fact")}
drift = json.load(open(os.environ.get("NAIVE_SHELL", "/dev/null"))) if False else None
base = {
    "playbook_path": "/firm/playbooks/vendor-nda-playbook.md",
    "ndas": {p: "conforms" for p in sorted(histories)},
    "silent_versions": sorted(silent),
    "term": {
        "playbook_standard": "three (3) years from disclosure",
        "practice": "five-year confidentiality terms went out",
        "document_path": sorted(histories)[0],
        "version": 2,
        "date": "2026-03-25",
    },
    "residuals": {
        "playbook_standard": "Reject any residual-knowledge clause outright.",
        "practice": "No deviation found in the mail record.",
        "document_path": sorted(histories)[0],
        "version": 2,
        "date": "2026-03-25",
    },
    "versions_reviewed": len(audit),
    "substantive_versions": counts["substantive"],
    "notices_only_versions": counts["notices_only"],
    "unchanged_versions": counts["unchanged"],
    "covered_substantive_versions": sum(
        r["change_class"] == "substantive" and bool(r["email_ids"]) for r in audit
    ),
    "silent_substantive_versions": len(silent),
    "covering_email_count": sum(len(r["email_ids"]) for r in audit),
    "authorized_substantive_versions": authority["present"],
    "unauthorized_substantive_versions": authority["absent"],
    "late_authorized_substantive_versions": authority["after_the_fact"],
    "version_audit": audit,
}
with open("drift.json", "w") as handle:
    json.dump(base, handle, indent=2)
EOF

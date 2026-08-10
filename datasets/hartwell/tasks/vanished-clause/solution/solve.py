"""Reference oracle for the vanished-clause task."""

import json
import os
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
MIN_BLOCK = 120
STATE = os.environ.get("WORKBENCH_STATE", "../state")

# This task-side copy is guarded by the marker-registry parity test.
DOC_MENTION_MARKERS: dict[str, tuple[str, ...]] = {
    "Billing & Time Entry Guidelines": (
        "billing guidelines",
        "time entry guidelines",
        "billing-guidelines",
    ),
    "Board Resolution Review — Veridian Energy Cooperative": (
        "board resolution review",
    ),
    "CAM Reconciliation Analysis — Pelican Bay Marina": ("cam reconciliation",),
    "Case Chronology — Cascadia Supplier Dispute": ("case chronology",),
    "Closing Checklist — Meridian Diagnostics Acquisition": ("closing checklist",),
    "Compliance Memorandum — Veridian Energy Cooperative": ("compliance memorandum",),
    "Disclosure Schedules — Meridian Diagnostics Acquisition": (
        "disclosure schedules",
    ),
    "Discovery Response Playbook": (
        "discovery response playbook",
        "discovery playbook",
        "discovery-responses",
    ),
    "Early Case Assessment — Goldleaf Hospitality Group": ("early case assessment",),
    "Engagement Letter (Standard Form)": ("engagement letter",),
    "Holdback Administration Memo — Solstice Vineyards": ("holdback administration",),
    "Lien Claim Summary — Arroyo Construction": ("lien claim summary",),
    "Litigation Hold Notice (Template)": ("litigation hold", "litigation-hold"),
    "Matter Intake Checklist": ("intake checklist", "matter-intake-checklist"),
    "Mutual NDA — Archway Court Reporting (Draft)": ("archway",),
    "Mutual NDA — BayMark IT Solutions (Draft)": ("baymark",),
    "Mutual NDA — Brightwater Trial Graphics (Draft)": ("brightwater",),
    "Mutual NDA — Cobalt Language Services (Draft)": ("cobalt",),
    "Mutual NDA — Harborlight Records Storage (Draft)": ("harborlight",),
    "Mutual NDA — Ironclad Discovery Services (Draft)": ("ironclad",),
    "Mutual NDA — LexiPoint Research (Draft)": ("lexipoint",),
    "Mutual NDA — Summit Staffing Partners (Draft)": ("summit",),
    "Mutual NDA — Trueline Process Servers (Draft)": ("trueline",),
    "Position Statement — Brightline Logistics (Draft)": ("position statement",),
    "Renewal Option Notice — Pelican Bay Marina (Draft)": ("renewal option notice",),
    "Scheduling Conference Report — Goldleaf Hospitality Group": (
        "scheduling conference report",
    ),
    "Software License and Support Agreement — Lumen Software (Draft)": (
        "license and support agreement",
        "license-and-support-agreement",
    ),
    "Stop Notice Service List — Arroyo Construction": ("stop notice service list",),
    "Support Services Statement of Work — Lumen Software (Draft)": (
        "statement of work",
        "support-services-sow",
    ),
    "Vendor Contract Comparison — Northgate Medical Group": (
        "vendor contract comparison",
    ),
    "Vendor NDA Playbook": ("nda playbook", "vendor-nda-playbook"),
    "Witness Interview Summaries — Brightline Logistics": (
        "witness interview summaries",
    ),
}


def rows(database: str, sql: str, *params: object) -> list[tuple]:
    with sqlite3.connect(f"file:{STATE}/{database}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def blocks(content: str) -> list[str]:
    return [
        block.strip()
        for block in content.split("\n\n")
        if len(block.strip()) >= MIN_BLOCK
    ]


def words(text: str) -> set[str]:
    return {word.strip(".,;:()'\"").lower() for word in text.split()} - {""}


def day_of(time: int) -> str:
    return (EPOCH + timedelta(days=time // 86400)).isoformat()


def main() -> int:
    history: dict[str, list[tuple[int, str, str, str, int]]] = {}
    titles: dict[str, str] = {}
    for name, path, version, author, content, comment, time in rows(
        "imanage.db",
        "SELECT d.name, d.path, v.version, v.author, v.content, v.comment, v.time "
        "FROM versions v JOIN documents d ON d.document_id = v.document_id "
        "ORDER BY d.path, v.version",
    ):
        titles[path] = name
        history.setdefault(path, []).append((version, author, content, comment, time))

    multi = {path: versions for path, versions in history.items() if len(versions) >= 2}
    if len(multi) != 32:
        sys.exit(f"expected 32 multi-version documents, found {len(multi)}")
    if set(titles[path] for path in multi) != set(DOC_MENTION_MARKERS):
        sys.exit("the multi-version corpus and document marker registry diverged")

    candidates = []
    for path, versions in multi.items():
        contents = [content for _, _, content, _, _ in versions]
        seen: set[str] = set()
        for content in contents:
            seen.update(blocks(content))
        for block in sorted(seen):
            presence = [block in content for content in contents]
            absents = [
                index
                for index, present in enumerate(presence)
                if not present and any(presence[:index])
            ]
            if not absents:
                continue
            first_absent = absents[0]
            if first_absent < 2 or not presence[first_absent - 2]:
                continue
            if any(presence[first_absent:]):
                continue
            dropped_words = words(block)
            replaced = any(
                len(dropped_words & words(other)) >= 0.6 * len(dropped_words)
                for other in blocks(contents[first_absent])
            )
            if not replaced:
                candidates.append((path, block, first_absent))

    if len(candidates) != 1:
        found = [(path, index) for path, _, index in candidates]
        sys.exit(f"expected exactly one silently dropped clause, found {found}")
    path, block, first_absent = candidates[0]
    version, author_id, _, comment, time = multi[path][first_absent]

    clause_noun = block.split()[1].strip(".,").lower()
    if clause_noun[:6] in comment.lower():
        sys.exit("the drop is announced in its comment; nothing silent to find")

    workspace = path.strip("/").split("/")[0]
    siblings = [
        other
        for other in multi
        if other != path and other.strip("/").split("/")[0] == workspace
    ]
    if not any(
        all(block not in content for _, _, content, _, _ in multi[other])
        for other in siblings
    ):
        sys.exit("expected a clean-history sibling document beside the answer")

    quotes = rows(
        "gmail.db",
        "SELECT time FROM messages WHERE body LIKE ? ORDER BY time",
        f"%{block}%",
    )
    if not quotes or all(quote_time <= time for (quote_time,) in quotes):
        sys.exit("expected the old clause text quoted in email after the drop")

    author = dict(
        rows(
            "imanage.db",
            "SELECT person_id, name FROM people WHERE person_id = ?",
            author_id,
        )
    )[author_id]

    numbers = dict(rows("imanage.db", "SELECT path, document_number FROM documents"))
    clean_documents = sorted(numbers[other] for other in multi if other != path)
    if len(clean_documents) != 31:
        sys.exit("the clean certification must cover all 31 other multi-version docs")

    day_texts: dict[str, list[str]] = {}
    for subject, mail_body, filenames, sent in rows(
        "gmail.db",
        "SELECT m.subject, m.body, "
        "COALESCE((SELECT group_concat(a.filename, ' ') FROM attachments a "
        "WHERE a.message_id = m.message_id), ''), m.time FROM messages m",
    ):
        day_texts.setdefault(day_of(sent), []).append(
            f"{subject} {mail_body} {filenames}".lower()
        )
    for chat_body, sent in rows(
        "slack.db",
        "SELECT m.body, m.time FROM messages m JOIN conversations c "
        "ON c.conversation_id = m.conversation_id WHERE c.kind != 'dm'",
    ):
        day_texts.setdefault(day_of(sent), []).append(chat_body.lower())

    unreviewed = []
    for doc_path, doc_versions in multi.items():
        markers = DOC_MENTION_MARKERS[titles[doc_path]]
        for saved_version, _, _, _, saved in doc_versions[1:]:
            mentioned = any(
                any(marker in text for marker in markers)
                for text in day_texts.get(day_of(saved), ())
            )
            if not mentioned:
                unreviewed.append(f"LEGAL!{numbers[doc_path]}.{saved_version}")
    if len(unreviewed) != 5:
        sys.exit(f"expected exactly five unreviewed revisions, found {unreviewed}")
    if f"LEGAL!{numbers[path]}.{first_absent + 1}" not in unreviewed:
        sys.exit("the dropping version itself must be unreviewed")

    head = block.split(". ", 1)[0]
    clause = {
        "document_path": path,
        "dropped_clause": f"{head} — dropped without replacement: {block[:140]}...",
        "dropped_in_version": version,
        "author": author,
        "date": day_of(time),
        "change_comment": comment,
        "clean_documents": clean_documents,
        "unreviewed_revisions": sorted(unreviewed),
    }
    json.dump(clause, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/bin/sh
# Reference solution: surveys EVERY multi-version document in the
# repository and diffs consecutive versions, because the instruction no
# longer names a document. A protection counts as silently dropped when a
# substantial paragraph that held steady across consecutive versions
# disappears with no similar replacement and never returns, while the
# version's own comment stays innocuous. The corpus is gated: many
# multi-version histories exist and exactly one of them drops a clause.
# Fails rather than answer from assumptions.
exec python3 - << 'EOF'
import json
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
MIN_BLOCK = 120  # characters; skips footers and bare headings


def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def blocks(content):
    return [b.strip() for b in content.split("\n\n") if len(b.strip()) >= MIN_BLOCK]


def words(text):
    return {w.strip(".,;:()'\"").lower() for w in text.split()} - {""}


history = {}
for path, version, author, content, comment, time in rows(
    "imanage.db",
    "SELECT d.path, v.version, v.author, v.content, v.comment, v.time "
    "FROM versions v JOIN documents d ON d.document_id = v.document_id "
    "ORDER BY d.path, v.version",
):
    history.setdefault(path, []).append((version, author, content, comment, time))

multi = {path: vs for path, vs in history.items() if len(vs) >= 2}
if len(multi) < 15:
    sys.exit(f"expected >= 15 multi-version documents, found {len(multi)}")
deep = [path for path, vs in multi.items() if len(vs) >= 3]
if len(deep) < 5:
    sys.exit(f"expected >= 5 documents with 3+ versions, found {len(deep)}")

candidates = []
for path, versions in multi.items():
    contents = [content for _, _, content, _, _ in versions]
    seen = set()
    for content in contents:
        seen.update(blocks(content))
    for block in sorted(seen):
        presence = [block in content for content in contents]
        absents = [
            i for i, present in enumerate(presence) if not present and any(presence[:i])
        ]
        if not absents:
            continue
        first_absent = absents[0]
        if first_absent < 2 or not presence[first_absent - 2]:
            continue  # never held across consecutive versions; not a stable clause
        if any(presence[first_absent:]):
            continue  # comes back later; an editing artifact, not a drop
        dropped_words = words(block)
        replaced = any(
            len(dropped_words & words(other)) >= 0.6 * len(dropped_words)
            for other in blocks(contents[first_absent])
        )
        if replaced:
            continue  # reworded, not removed
        candidates.append((path, block, first_absent))

if len(candidates) != 1:
    sys.exit(
        f"expected exactly one silently dropped clause, found {len(candidates)}: "
        f"{[(path, index) for path, _, index in candidates]}"
    )
path, block, first_absent = candidates[0]
version, author_id, _, comment, time = multi[path][first_absent]

# The drop must be silent: the comment does not name the clause.
clause_noun = block.split()[1].strip(".,").lower()
if clause_noun[:6] in comment.lower():
    sys.exit("the drop is announced in its comment; nothing silent to find")

# A sibling multi-version document in the same workspace never carried the
# clause — the survey, not a name, must have discriminated.
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

# The email record still quotes the old clause AFTER the drop — the wrong
# anchor must exist, and must not fool the version diff.
quotes = rows(
    "gmail.db",
    "SELECT time FROM messages WHERE body LIKE ? ORDER BY time",
    f"%{block}%",
)
if not quotes or all(quote_time <= time for (quote_time,) in quotes):
    sys.exit("expected the old clause text quoted in email after the drop")

author = dict(
    rows("imanage.db", "SELECT person_id, name FROM people WHERE person_id = ?",
         author_id)
)[author_id]

# Attestation by enumeration: every other multi-version document is
# certified clean by the same survey that found the drop.
numbers = dict(rows("imanage.db", "SELECT path, document_number FROM documents"))
clean_documents = sorted(numbers[other] for other in multi if other != path)
if len(clean_documents) != len(multi) - 1:
    sys.exit("the clean certification must cover every other multi-version doc")

head = block.split(". ", 1)[0]
clause = {
    "document_path": path,
    "dropped_clause": f"{head} — dropped without replacement: {block[:140]}...",
    "dropped_in_version": version,
    "author": author,
    "date": (EPOCH + timedelta(days=time // 86400)).isoformat(),
    "change_comment": comment,
    "clean_documents": clean_documents,
}
with open("clause.json", "w") as handle:
    json.dump(clause, handle, indent=2)
print("clause.json written")
EOF

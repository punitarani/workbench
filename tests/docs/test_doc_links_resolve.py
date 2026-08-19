"""Every relative link in a tracked markdown file must resolve.

Docs are an unread surface: nothing imports them, so nothing fails when
they rot. This tree has already paid for that twice — a defect in a
surface no test reads survives every green run until a human happens to
click.

The rot is silent and systematic rather than occasional. Un-nesting a
package tree moved every `src/<pkg>/` doc one level up and left sixteen
`../../../docs/...` hrefs overshooting the repo root; renaming a docs
folder stranded the links into it. Neither showed up in a diff, because
both files still existed and only the path between them had changed.

Anchors are checked too. A link to a heading that was later reworded is
a link that silently lands at the top of the right file, which reads as
working and is not.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKIP = ("out", "jobs", ".venv", ".git", ".workbench")

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_HEADING = re.compile(r"#{1,6}\s+(.*)")


def _slugs(path: Path) -> set[str]:
    """GitHub's heading slugs: strip punctuation, lowercase, hyphenate."""
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = _HEADING.match(line)
        if heading:
            text = re.sub(r"[^\w\s-]", "", heading.group(1).lower()).strip()
            found.add(re.sub(r"\s+", "-", text))
    return found


def _tracked_markdown() -> list[Path]:
    return sorted(
        p
        for p in REPO.rglob("*.md")
        if not any(part in SKIP for part in p.relative_to(REPO).parts)
    )


MARKDOWN = _tracked_markdown()


def test_the_audit_found_files_to_check() -> None:
    """Guard the guard: a glob that matches nothing passes vacuously."""

    assert len(MARKDOWN) >= 50, len(MARKDOWN)


@pytest.mark.parametrize("doc", MARKDOWN, ids=lambda p: str(p.relative_to(REPO)))
def test_every_relative_link_resolves(doc: Path) -> None:
    broken = []
    for match in _LINK.finditer(doc.read_text(encoding="utf-8")):
        href = match.group(1)
        if href.startswith(("http://", "https://", "mailto:")):
            continue
        path, _, anchor = href.partition("#")
        target = doc.parent / path if path else doc
        if not target.exists():
            broken.append(f"{href} -> no such file")
        elif anchor and target.suffix == ".md" and anchor not in _slugs(target):
            broken.append(f"{href} -> no such heading")
    assert not broken, f"{doc.relative_to(REPO)}: " + "; ".join(broken)

"""Where a document lands in a file room, and what it is called there.

This is one rule with two readers, and it lived in only one of them.

The projection that builds the served surface derives an on-disk name
from a document's declared path — and it keeps only the *top-level*
segment, discarding every intermediate directory, because a file room is
a flat set of workspaces rather than a filesystem tree. So

    engagements/northmoor/sandhurst-add-on/diligence-status-tracker.xlsx
    engagements/northmoor/sandhurst-platform/diligence-status-tracker.xlsx

are two documents on two different matters that become **one file**, the
second overwriting the first.

The referee, meanwhile, must refuse a document whose file another
document already holds — and it was comparing the *declared* paths, which
are distinct. Measured on a real world: 32 documents, 32 distinct
declared paths, 30 distinct files. Two documents lost, and the guard
written to prevent exactly that reported nothing.

A rule that two components must agree on belongs to neither of them.
Both now read it here, so a change to the naming cannot leave the guard
checking something the file room does not do.
"""

from __future__ import annotations

# What each content format is called on disk when the author gave no
# usable suffix.
FORMAT_EXTENSIONS: dict[str, str] = {
    "markdown": "md",
    "spreadsheet": "xlsx",
    "formatted": "docx",
    "slides": "pptx",
}

# What each format may legitimately be called. A formatted document is a
# .docx normally and a .pdf when it is issued; tabular content is a .xlsx
# normally and a .csv when it is an extract. Anything else is the author
# mislabelling their own work, and the format wins.
ALLOWED_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "markdown": ("md", "txt", "csv"),
    "spreadsheet": ("xlsx", "csv"),
    "formatted": ("docx", "pdf"),
    "slides": ("pptx",),
}

# Where a document lands when its author gave a bare filename. Every
# document belongs to some workspace; without this a path of "brief.docx"
# made the file its own workspace and materialized as the directory
# "brief.docx/brief.docx".
DEFAULT_WORKSPACE = "firm"


def workspace_of(path: str) -> str:
    """The workspace: the top-level path segment, `/legal/... -> legal`.

    Folded to lower case because authors are not consistent and a file
    room is not case-sensitive. One world produced both ``Engagements``
    and ``engagements``, which the surface served as two workspaces
    holding one engagement's papers between them.
    """

    segments = [segment for segment in path.strip("/").split("/") if segment]
    return segments[0].casefold() if len(segments) > 1 else DEFAULT_WORKSPACE


def extension_of(path: str, content_format: str) -> str:
    """The suffix the file will actually carry.

    A name must never lie about its bytes. An author who declares a
    workbook and names it `.docx` produced a file Word cannot open, and an
    agent that trusts the extension is misled by the environment rather
    than by the work — so the format wins the disagreement.
    """

    canonical = FORMAT_EXTENSIONS.get(content_format, content_format)
    basename = path.rsplit("/", 1)[-1]
    if "." not in basename:
        return canonical
    suffix = basename.rsplit(".", 1)[-1].lower()
    allowed = ALLOWED_EXTENSIONS.get(content_format)
    if allowed is None:
        return suffix
    return suffix if suffix in allowed else canonical


def filed_name(path: str, content_format: str) -> str:
    """The file this document will actually become: `workspace/stem.ext`.

    **This, not the declared path, is what can collide.** Two documents
    differing only in an intermediate directory produce one file, and a
    guard comparing declared paths sees two distinct strings.
    """

    basename = path.rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return f"{workspace_of(path)}/{stem}.{extension_of(path, content_format)}"


__all__ = [
    "ALLOWED_EXTENSIONS",
    "DEFAULT_WORKSPACE",
    "FORMAT_EXTENSIONS",
    "extension_of",
    "filed_name",
    "workspace_of",
]

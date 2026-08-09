"""Workspace layout guards: PEP 420 namespace stays a namespace."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_core_imports() -> None:
    import workbench.core

    assert workbench.core.__doc__


def test_namespace_root_has_no_init() -> None:
    offenders = [
        path
        for path in REPO.glob("*/src/workbench/__init__.py")
        if path.is_file()
    ]
    assert offenders == [], (
        f"src/workbench must stay a PEP 420 namespace; delete {offenders}"
    )

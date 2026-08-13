"""Workspace layout guards for the single-distribution tree."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_core_imports() -> None:
    import workbench.core

    assert workbench.core.__doc__


def test_single_package_root() -> None:
    assert (REPO / "src" / "workbench" / "__init__.py").is_file(), (
        "workbench is one regular package; src/workbench/__init__.py must exist"
    )


def test_no_stray_member_trees() -> None:
    strays = [path for path in REPO.glob("*/src/workbench") if path.is_dir()]
    assert strays == [], (
        f"member-style src trees must not reappear; found {strays}"
    )

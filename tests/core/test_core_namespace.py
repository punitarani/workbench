"""Workspace layout guards for the flattened tree.

`src/workbench/core` said the project's name twice, so the `workbench`
level was removed and the eight subpackages became top-level modules.
The distribution is still `workbench`; only the import spelling changed.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PACKAGES = frozenset(
    {
        "adapters",
        "analysis",
        "artifacts",
        "core",
        "environment",
        "simulation",
        "tools",
        "workplaces",
    }
)


def test_core_imports() -> None:
    import core

    assert core.__doc__


def test_every_package_is_a_regular_package() -> None:
    """Each of the eight carries an `__init__.py`.

    They are top-level modules now, so a missing init makes one an
    implicit namespace package — which imports fine here and silently
    ships nothing in the wheel.
    """

    missing = [
        name
        for name in sorted(PACKAGES)
        if not (REPO / "src" / name / "__init__.py").is_file()
    ]
    assert missing == [], f"not regular packages: {missing}"


def test_src_is_not_itself_a_package() -> None:
    """`src/` is a path root, never an importable name.

    An `__init__.py` here would make every module `src.core`, `src.tools`
    and so on, reintroducing the nesting the flatten removed and breaking
    every import in the tree.
    """

    assert not (REPO / "src" / "__init__.py").exists()


def test_no_unlisted_top_level_package() -> None:
    """A new top-level module must be declared, in three places.

    Adding a directory under `src/` claims that name globally for anyone
    who installs this distribution, so it needs a layering rule
    (`test_layering.ALLOWED`), an entry in `[tool.uv.build-backend]
    module-name`, and a line here. This test fails until all three exist.
    """

    found = {
        p.name
        for p in (REPO / "src").iterdir()
        if p.is_dir() and not p.name.startswith("__")
    }
    assert found == set(PACKAGES), (
        f"undeclared: {sorted(found - PACKAGES)}; missing: {sorted(PACKAGES - found)}"
    )


def test_no_stray_member_trees() -> None:
    strays = [path for path in REPO.glob("*/src/workbench") if path.is_dir()]
    assert strays == [], f"member-style src trees must not reappear; found {strays}"

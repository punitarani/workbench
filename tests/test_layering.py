"""Layering rules, enforced.

Packaging never actually policed these — all subpackages install into one
venv — so the import graph is asserted here instead. Since the tree was
flattened these are also the *only* thing keeping eight top-level modules
honest: with no shared package prefix, nothing but this test distinguishes
`from core import ...` inside `simulation` (legal) from the same line
inside `tools` (also legal) from `from simulation import ...` inside
`tools` (not). Rules mirror AGENTS.md:

    core         imports no other workbench subpackage
    tools        imports core only
    environment  imports core, tools, and artifacts (the only consumer
                 of rendering)
    simulation   imports core only (never tools: offstage must not see
                 the agent-facing surface)
    workplaces   imports core and simulation
    adapters     imports core and tools (never simulation or workplaces:
                 the eval harness must not reach offstage)
    artifacts    imports core only
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

ALLOWED: dict[str, frozenset[str]] = {
    "core": frozenset(),
    "tools": frozenset({"core"}),
    "environment": frozenset({"core", "tools", "artifacts"}),
    "simulation": frozenset({"core"}),
    "workplaces": frozenset({"core", "simulation"}),
    "adapters": frozenset({"core", "tools"}),
    "artifacts": frozenset({"core"}),
    # Analysis reads finished worlds — the log and the databases projected
    # from it — and never runs inside the simulation, so it may see core
    # and tools but nothing may depend on it.
    "analysis": frozenset({"core", "tools"}),
}


def _sibling_imports(path: Path) -> set[str]:
    """Which of the eight top-level packages this file imports.

    Before the flatten these were spelled `workbench.<name>` and the
    prefix identified them. Now they are bare top-level names, so
    membership in ALLOWED is what marks an import as internal — which
    means a new subpackage without a rule is invisible here, and
    `test_every_subpackage_has_a_rule` is what catches that.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] in ALLOWED:
                    found.add(parts[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            if parts[0] in ALLOWED:
                found.add(parts[0])
    return found


def test_every_subpackage_has_a_rule() -> None:
    subpackages = {
        p.name for p in SRC.iterdir() if p.is_dir() and not p.name.startswith("__")
    }
    assert subpackages <= set(ALLOWED), (
        f"new subpackage(s) {sorted(subpackages - set(ALLOWED))} need a layering rule"
    )


def test_import_graph_respects_layering() -> None:
    violations: list[str] = []
    for name, allowed in ALLOWED.items():
        package = SRC / name
        if not package.exists():
            continue
        for path in sorted(package.rglob("*.py")):
            offending = _sibling_imports(path) - allowed - {name}
            if offending:
                rel = path.relative_to(SRC.parent)
                violations.append(f"{rel}: imports {sorted(offending)}")
    assert violations == [], "\n".join(violations)

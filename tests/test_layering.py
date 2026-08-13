"""Layering rules, enforced.

Packaging never actually policed these — all subpackages install into one
venv — so the import graph is asserted here instead. Rules mirror AGENTS.md:

    core         imports no other workbench subpackage
    tools        imports core only
    environment  imports core and tools
    simulation   imports core only (never tools: offstage must not see
                 the agent-facing surface)
    workplaces   imports core and simulation
    adapters     imports core and tools (never simulation or workplaces:
                 the eval harness must not reach offstage)
    artifacts    imports core only
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "workbench"

ALLOWED: dict[str, frozenset[str]] = {
    "core": frozenset(),
    "tools": frozenset({"core"}),
    "environment": frozenset({"core", "tools"}),
    "simulation": frozenset({"core"}),
    "workplaces": frozenset({"core", "simulation"}),
    "adapters": frozenset({"core", "tools"}),
    "artifacts": frozenset({"core"}),
}


def _workbench_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "workbench" and len(parts) > 1:
                    found.add(parts[1])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            if parts[0] == "workbench" and len(parts) > 1:
                found.add(parts[1])
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
            offending = _workbench_imports(path) - allowed - {name}
            if offending:
                rel = path.relative_to(SRC.parent.parent)
                violations.append(f"{rel}: imports workbench.{sorted(offending)}")
    assert violations == [], "\n".join(violations)

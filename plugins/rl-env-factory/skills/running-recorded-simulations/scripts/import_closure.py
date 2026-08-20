"""Which modules a runner actually reaches, so you know what is frozen.

During a long recording, anything the runner imports is frozen: changing it
makes the first half of the record and the second half two different
worlds, and nothing will tell you. Everything outside that closure is
downstream and can be rebuilt freely.

Reading the runner's own import list understates the answer, because
imports are transitive and can be routed through a registry. Asking the
running process does not work either: CPython opens a source file,
compiles it and closes it, so `lsof` shows no `.py` files at all --
including the ones it is certainly executing. It answers "not reached" for
everything, which is a check that always passes.

    python import_closure.py run.py --src src --check tools analysis
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _module_file(root: Path, name: str) -> Path | None:
    parts = name.split(".")
    for candidate in (
        root.joinpath(*parts).with_suffix(".py"),
        root.joinpath(*parts, "__init__.py"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _imports(path: Path, root: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    # Parenthesised deliberately: the bare form is Python 3.14 only, and a
    # script bundled with a skill has to run on whatever the reader has.
    except OSError, SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (`from . import x`, `from ..pkg import y`) were
            # skipped here, and skipping them fails in the dangerous
            # direction: a package reached only through relative imports is
            # reported "not reached -- safe to edit" while the runner is
            # executing it. Resolve them against the importing module's own
            # position in the tree.
            base = node.module or ""
            if node.level:
                try:
                    here = path.resolve().relative_to(root).parts
                except ValueError:
                    continue
                # One dot means "the package this module lives in", which is
                # the parent directory whether the file is `__init__.py` or an
                # ordinary module. Each extra dot climbs one more level.
                package = list(here[:-1])
                climb = node.level - 1
                if climb:
                    package = package[:-climb] if climb <= len(package) else []
                base = ".".join([*package, base]) if base else ".".join(package)
            if not base:
                continue
            found.add(base)
            found |= {f"{base}.{alias.name}" for alias in node.names}
    return found


def closure(entry: Path, root: Path) -> set[Path]:
    seen: set[Path] = set()
    queue = [entry.resolve()]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for name in _imports(current, root):
            found = _module_file(root, name)
            if found and found not in seen:
                queue.append(found)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry", type=Path, help="the runner's entry point")
    parser.add_argument("--src", type=Path, default=Path("src"))
    parser.add_argument(
        "--check",
        nargs="*",
        default=[],
        help="top-level packages to report as frozen or safe",
    )
    args = parser.parse_args()
    root = args.src.resolve()
    if not args.entry.is_file():
        print(f"no entry point at {args.entry}", file=sys.stderr)
        return 2

    reached = closure(args.entry, root)
    by_package: dict[str, int] = {}
    for path in reached:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        by_package[relative.parts[0]] = by_package.get(relative.parts[0], 0) + 1

    for package in sorted(by_package):
        print(f"  {package:16s} {by_package[package]:3d} modules")
    bad = False
    for package in args.check:
        if package in by_package:
            print(f"  {package}: REACHED -- frozen while the run is live")
            bad = True
        else:
            print(f"  {package}: not reached -- safe to edit")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

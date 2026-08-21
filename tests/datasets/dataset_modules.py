"""Load one dataset's build module by path, not by name.

Three datasets each ship a `build_tasks.py`. `sys.path.insert(0, .../merrick)`
followed by `import build_tasks` gets merrick's module *only if nothing has
already imported a `build_tasks`* — and when the whole suite runs,
`datasets/hartwell/test_build_tasks.py` is collected first, so
`sys.modules["build_tasks"]` is already hartwell's and the insert does
nothing. Every merrick gate test then failed with `module 'build_tasks'
has no attribute '_structural_absences'`.

Thirteen tests, and each of them passed when run alone — which is how the
file was written and how it was checked. A test that passes in isolation
and cannot pass in the suite is the same disease as a test that cannot
fail: it is not measuring what its name says, and the green tick is
worth nothing.

Loading by path with a dataset-qualified module name removes the
collision rather than ordering around it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_DATASETS = Path(__file__).resolve().parents[2] / "datasets"


def dataset_module(dataset: str, name: str) -> ModuleType:
    """`datasets/<dataset>/<name>.py`, under a name nothing else can claim."""

    qualified = f"_workbench_dataset_{dataset}_{name}"
    if (cached := sys.modules.get(qualified)) is not None:
        return cached
    path = _DATASETS / dataset / f"{name}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    # The dataset's own directory still has to be importable: these build
    # modules do `from criteria_base import ...` on their siblings.
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


def merrick_build_tasks() -> ModuleType:
    return dataset_module("merrick", "build_tasks")

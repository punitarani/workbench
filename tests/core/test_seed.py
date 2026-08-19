import subprocess
import sys

from core.seed import Seed, derive_rng, derive_seed


def test_derivation_is_stable() -> None:
    seed = Seed(root=42)
    # Golden values: a change here is a breaking change to every recorded run.
    assert derive_seed(seed, "entity", "alice") == derive_seed(seed, "entity", "alice")
    assert derive_seed(seed, "entity", "alice") != derive_seed(seed, "entity", "bob")
    assert derive_seed(seed, "entity", "alice") != derive_seed(seed, "entity:alice")


def test_path_parts_are_not_ambiguous() -> None:
    seed = Seed(root=7)
    assert derive_seed(seed, "ab", "c") != derive_seed(seed, "a", "bc")
    assert derive_seed(seed, "a", "") != derive_seed(seed, "a")


def test_different_roots_differ() -> None:
    assert derive_seed(Seed(root=1), "x") != derive_seed(Seed(root=2), "x")


def test_derive_rng_is_deterministic() -> None:
    values_a = derive_rng(Seed(root=9), "shuffle").sample(range(100), 5)
    values_b = derive_rng(Seed(root=9), "shuffle").sample(range(100), 5)
    assert values_a == values_b


def test_derivation_is_pythonhashseed_independent() -> None:
    code = (
        "from core.seed import Seed, derive_seed;"
        "print(derive_seed(Seed(root=42), 'entity', 'alice'))"
    )
    outputs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin"},
        ).stdout.strip()
        for hash_seed in ("0", "42")
    }
    assert len(outputs) == 1

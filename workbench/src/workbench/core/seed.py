"""Seed derivation: every source of randomness flows from one root seed.

Derivation is blake2b-based so it is stable across processes, platforms, and
PYTHONHASHSEED. Changing the domain prefix or encoding invalidates every
recorded run.
"""

import hashlib
import random

from pydantic import BaseModel, Field

_DOMAIN = b"workbench.seed.v1"


class Seed(BaseModel, frozen=True):
    root: int = Field(ge=0, lt=2**64)


def derive_seed(seed: Seed, *path: str) -> int:
    digest = hashlib.blake2b(_DOMAIN, digest_size=8)
    digest.update(seed.root.to_bytes(8, "big"))
    for part in path:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return int.from_bytes(digest.digest(), "big")


def derive_rng(seed: Seed, *path: str) -> random.Random:
    return random.Random(derive_seed(seed, *path))

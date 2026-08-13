"""Canonical JSON bytes and content hashes for models and plain data."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel

_DOMAIN = b"workbench.hash.v1"


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    digest = hashlib.blake2b(_DOMAIN, digest_size=32)
    digest.update(canonical_json_bytes(value))
    return digest.hexdigest()

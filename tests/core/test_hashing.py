from pydantic import BaseModel

from core.hashing import canonical_json_bytes, content_hash


class Point(BaseModel):
    x: int
    y: str


def test_canonical_bytes_sort_keys() -> None:
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_bytes_accept_models() -> None:
    assert canonical_json_bytes(Point(x=1, y="z")) == b'{"x":1,"y":"z"}'


def test_content_hash_is_stable_and_distinct() -> None:
    first = content_hash(Point(x=1, y="z"))
    assert first == content_hash(Point(x=1, y="z"))
    assert first != content_hash(Point(x=2, y="z"))
    assert len(first) == 64
    int(first, 16)


def test_unicode_is_not_escaped() -> None:
    assert canonical_json_bytes({"name": "Müller"}) == '{"name":"Müller"}'.encode()

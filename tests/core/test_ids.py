import pytest
from pydantic import ValidationError

from core.ids import IdMinter


def test_mint_is_sequential_and_zero_padded() -> None:
    minter = IdMinter()
    assert minter.mint("msg") == "msg-000001"
    assert minter.mint("msg") == "msg-000002"
    assert minter.mint("thr") == "thr-000001"


def test_minter_state_round_trips() -> None:
    minter = IdMinter()
    minter.mint("msg")
    minter.mint("msg")
    restored = IdMinter.model_validate_json(minter.model_dump_json())
    assert restored.mint("msg") == "msg-000003"


def test_minter_serialization_is_key_order_independent() -> None:
    a = IdMinter()
    a.mint("msg")
    a.mint("thr")
    b = IdMinter()
    b.mint("thr")
    b.mint("msg")
    assert a.model_dump_json() == b.model_dump_json()


def test_prefix_must_be_slug() -> None:
    minter = IdMinter()
    with pytest.raises(ValidationError):
        minter.mint("Not A Slug")

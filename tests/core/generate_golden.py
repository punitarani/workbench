"""Regenerates the golden world log when serialization intentionally changes."""

from test_golden_log import GOLDEN, fixture_bytes

if __name__ == "__main__":
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_bytes(fixture_bytes())
    print(f"wrote {GOLDEN} ({GOLDEN.stat().st_size} bytes)")

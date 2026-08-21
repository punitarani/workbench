"""Measure a generated world against the committed bands.

    uv run python scripts/fidelity_report.py \
        --state out/calder/epoch-6mo/bundle/state \
        --log out/calder/epoch-6mo/world.jsonl \
        --out docs/fidelity/FIDELITY-REPORT.md

Exits non-zero when any band fails, so CI can gate on it. Pass
``--allow-fail`` to write the report without failing the process (how the
v1 baseline is produced — v1 is *expected* to fail most of them).
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from analysis.fidelity import (  # noqa: E402
    BANDS_PATH,
    evaluate,
    load_bands,
    measure,
    render_markdown,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--bands", type=Path, default=BANDS_PATH)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--title", default="Fidelity report")
    parser.add_argument("--context", default="")
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args(argv)

    bands = load_bands(args.bands)
    measurements = measure(args.state, args.log)
    results = evaluate(measurements, bands)
    report = render_markdown(results, title=args.title, context=args.context)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)

    counts = summarize(results)
    print(
        f"bands: {counts['PASS']} pass, {counts['FAIL']} fail, "
        f"{counts['ABSENT']} absent"
    )
    for result in results:
        if result.verdict == "FAIL":
            print(
                f"  FAIL {result.metric}: observed "
                f"{result.observed:,.4g} against {result.band.rendered()}"
            )
    return 0 if args.allow_fail or counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

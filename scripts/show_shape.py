"""Print what a surface actually looks like, before writing a query against it.

    ./.venv/bin/python scripts/show_shape.py out/merrick/bundle/state/meetings.db
    ./.venv/bin/python scripts/show_shape.py .../meetings.db utterances
    ./.venv/bin/python scripts/show_shape.py .../tests/oracle.json

A wrong field does not raise. It falls through to a default, produces a
plausible number, and the analysis reads as evidence. On 2026-08-23 that
cost, in one session:

* `clio.display_number` read as matter identity -- it is the *client*, and
  its distinctive tokens are partner surnames;
* `Band.low` / `Band.high`, where the fields are `min` and `max`: the
  comparison fell through and reported all 36 band failures as missing by
  exactly 1.0x, which is the answer that says "no gate needed";
* three attempts at a dump for `off-sense-register`, each built with a
  guessed row key, each scoring the empty-register floor because nothing
  matched.

Every one printed the real names somewhere on screen first. The law was
written down at 04:12 and broken at 04:35, 04:45 and 04:52, so the fix is
not another sentence about care. It is one command that costs three
seconds, and this is it.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SAMPLE = 200


def _json(path: Path) -> None:
    loaded = json.loads(path.read_text())
    if isinstance(loaded, list):
        loaded = {"<top-level list>": loaded}
    print(f"{path}\n")
    for key, value in loaded.items():
        if isinstance(value, list):
            print(f"  {key}: list of {len(value)}")
            if value and isinstance(value[0], dict):
                print(f"      fields: {list(value[0])}")
                print(f"      row 0 : {value[0]}")
                for field in value[0]:
                    seen = Counter(
                        json.dumps(row.get(field), sort_keys=True)
                        for row in value[:SAMPLE]
                        if isinstance(row, dict)
                    )
                    top = ", ".join(f"{v}×{n}" for v, n in seen.most_common(3))
                    print(f"        {field:<18}{len(seen):>4} distinct   {top[:60]}")
            elif value:
                print(f"      first : {value[0]!r}")
        elif isinstance(value, dict):
            print(f"  {key}: dict {list(value)[:8]}")
        else:
            print(f"  {key}: {value!r}")


def _sqlite(path: Path, table: str | None) -> None:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = [
        name
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    print(f"{path}\n  tables: {tables}\n")
    for name in tables if table is None else [table]:
        if name not in tables:
            raise SystemExit(f"no table {name!r}; there are {tables}")
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
        (count,) = connection.execute(f"SELECT count(*) FROM {name}").fetchone()  # noqa: S608
        print(f"  {name}  ({count} rows)")
        print(f"    columns: {columns}")
        rows = connection.execute(f"SELECT * FROM {name} LIMIT 1").fetchall()  # noqa: S608
        if rows:
            for column, value in zip(columns, rows[0], strict=False):
                shown = repr(value)
                print(f"      {column:<22}{shown[:64]}")
        print()
    connection.close()


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit(__doc__)
    path = Path(argv[0])
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    if path.suffix == ".json":
        _json(path)
    else:
        _sqlite(path, argv[1] if len(argv) > 1 else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Run every ``sql/*.sql`` against Trino and save JSON results.

The host talks to Trino through the NodePort published on ``localhost:8080``.
Each result is written as ``<out-dir>/phase5_<stem>.json`` with the SQL text,
the columns and the rows, so ``scripts/verify-results.py`` can compare a fresh
run with the committed reference.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import trino

ROOT = Path(__file__).resolve().parents[1]
HOST = "localhost"
PORT = 8080


def run_query(sql: str) -> tuple[list[str], list[list]]:
    """Execute one statement; return ``(columns, rows as plain lists)``.

    Values are cast to ``str`` so the JSON is stable regardless of the Python
    type Trino's driver returns (Decimal, datetime, ...).
    """
    conn = trino.dbapi.connect(
        host=HOST, port=PORT, user="lakehouse", catalog="lakehouse", schema="nyc"
    )
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [[str(v) for v in r] for r in cur.fetchall()]
    return cols, rows


def main() -> None:
    """Run every ``sql/*.sql`` file; write ``<out-dir>/phase5_<name>.json``."""
    parser = argparse.ArgumentParser()
    # --out-dir lets verify.ps1 write to a temp folder without touching the
    # committed reference files.
    parser.add_argument("--out-dir", default=str(ROOT / "experiments"))
    args = parser.parse_args()
    exp = Path(args.out_dir)
    exp.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "sql").glob("*.sql")):
        sql = path.read_text(encoding="utf-8").strip().rstrip(";")
        cols, rows = run_query(sql)
        out = exp / f"phase5_{path.stem}.json"
        out.write_text(
            json.dumps(
                {"sql": sql, "columns": cols, "rows": rows, "row_count": len(rows)}, indent=2
            ),
            encoding="utf-8",
        )
        print(f"{path.name} -> {out.name}: {len(rows)} rows")
        # Echo the first rows so the operator sees the result immediately.
        for row in rows[:12]:
            print("  ", row)


if __name__ == "__main__":
    main()

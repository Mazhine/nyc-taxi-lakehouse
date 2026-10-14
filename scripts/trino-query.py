"""Run sql/*.sql against Trino (host -> localhost:8080) and save JSON results."""

from __future__ import annotations

import json
from pathlib import Path

import trino

ROOT = Path(__file__).resolve().parents[1]
HOST = "localhost"
PORT = 8080


def run_query(sql: str) -> tuple[list[str], list[list]]:
    """Execute one statement; return (columns, rows as plain lists)."""
    conn = trino.dbapi.connect(
        host=HOST, port=PORT, user="lakehouse", catalog="lakehouse", schema="nyc"
    )
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [[str(v) for v in r] for r in cur.fetchall()]
    return cols, rows


def main() -> None:
    """Run every sql/*.sql file; write experiments/phase5_<name>.json."""
    exp = ROOT / "experiments"
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
        for row in rows[:12]:
            print("  ", row)


if __name__ == "__main__":
    main()

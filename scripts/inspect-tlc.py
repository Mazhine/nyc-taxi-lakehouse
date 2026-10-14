"""Inspect TLC parquet schemas per month; write JSON report to experiments/."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXP = ROOT / "experiments"
EXP.mkdir(exist_ok=True)


def inspect(path: Path) -> dict:
    """Return schema + row count for one parquet file."""
    pf = pq.ParquetFile(path)
    schema = [(f.name, str(f.type)) for f in pf.schema_arrow]
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "rows": pf.metadata.num_rows,
        "num_row_groups": pf.metadata.num_row_groups,
        "columns": [n for n, _ in schema],
        "dtypes": dict(schema),
    }


def main() -> None:
    """Write experiments/tlc_schema_report.json and print a diff summary."""
    files = sorted(DATA.glob("yellow_tripdata_*.parquet"))
    report = [inspect(f) for f in files]
    out = EXP / "tlc_schema_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    base = set(report[0]["columns"])
    print(f"inspected {len(report)} files => {out.name}")
    for entry in report:
        cols = set(entry["columns"])
        extra = sorted(cols - base)
        missing = sorted(base - cols)
        print(
            f"{entry['file']}: rows={entry['rows']} cols={len(cols)} "
            f"extra_vs_first={extra} missing_vs_first={missing}"
        )
    # pairwise drift 2019 vs 2024-01
    by_file = {e["file"]: e for e in report}
    old = by_file.get("yellow_tripdata_2019-01.parquet", {})
    new = by_file.get("yellow_tripdata_2024-01.parquet", {})
    if old and new:
        print("2019-01 cols:", old["columns"])
        print("2024-01 cols:", new["columns"])
        type_changes = {
            c: (old["dtypes"].get(c), new["dtypes"].get(c))
            for c in set(old["columns"]) & set(new["columns"])
            if old["dtypes"].get(c) != new["dtypes"].get(c)
        }
        print("type_changes_2019_vs_2024:", json.dumps(type_changes, indent=2))


if __name__ == "__main__":
    main()

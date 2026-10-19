"""Offline quarantine breakdown by rule (no cluster required).

Reads the raw monthly parquet files from ``data/`` and applies the *same* rule
expressions as :func:`src.ingestion.ingest.split_valid_quarantine_df`, then
counts how many rows each rule rejects. This is a pure reproducibility aid: it
lets the per-rule table in the README be recomputed without bringing the
lakehouse up. It is not part of the ingestion path.

Usage::

    .\\.venv\\Scripts\\python.exe scripts\\quarantine-reasons.py
    # -> experiments/phase4_quarantine_reasons.json
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import pandas as pd

# Same five business rules as the Spark job, one callable per rule.
RULES = {
    "pickup_before_dropoff": lambda d: d["tpep_pickup_datetime"] > d["tpep_dropoff_datetime"],
    "trip_distance_invalid": lambda d: (d["trip_distance"] < 0) | d["trip_distance"].isna(),
    "fare_amount_invalid": lambda d: (d["fare_amount"] < 0) | d["fare_amount"].isna(),
    "total_amount_invalid": lambda d: (d["total_amount"] < 0) | d["total_amount"].isna(),
    "location_ids_invalid": lambda d: (
        (d["PULocationID"] <= 0)
        | d["PULocationID"].isna()
        | (d["DOLocationID"] <= 0)
        | d["DOLocationID"].isna()
    ),
}

# Only the columns the rules need (keeps memory small on 20 M rows).
COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
    "total_amount",
    "PULocationID",
    "DOLocationID",
]


def main() -> int:
    """Compute per-rule counts and write the JSON artifact."""
    repo = Path(__file__).resolve().parents[1]
    totals = {name: 0 for name in RULES}
    per_month: dict[str, dict[str, int]] = {}
    input_rows = 0
    quarantined_rows = 0
    multi_reason = 0

    for path in sorted(glob.glob(str(repo / "data" / "yellow_tripdata_2024-0*.parquet"))):
        month = os.path.basename(path).replace("yellow_tripdata_", "").replace(".parquet", "")
        frame = pd.read_parquet(path, columns=COLUMNS)
        # The contract types pickups/dropoffs as timestamps; coerce the same way.
        frame["tpep_pickup_datetime"] = pd.to_datetime(
            frame["tpep_pickup_datetime"], errors="coerce"
        )
        frame["tpep_dropoff_datetime"] = pd.to_datetime(
            frame["tpep_dropoff_datetime"], errors="coerce"
        )
        input_rows += len(frame)
        masks = {name: fn(frame) for name, fn in RULES.items()}
        bad = pd.Series(False, index=frame.index)
        for mask in masks.values():
            bad = bad | mask
        counts = {name: int(mask.sum()) for name, mask in masks.items()}
        multi_reason += int((sum(m.astype(int) for m in masks.values()) > 1).sum())
        quarantined_rows += int(bad.sum())
        for name in RULES:
            totals[name] += counts[name]
        per_month[month] = {"input": len(frame), "quarantined": int(bad.sum()), **counts}
        print(f"{month}: input={len(frame)} quarantined={int(bad.sum())} {counts}", flush=True)

    result = {
        "note": (
            "Offline recomputation of the ingest rule logic over data/*.parquet "
            "(same expressions as src/ingestion/ingest.py)."
        ),
        "input_rows": input_rows,
        "quarantined_rows": quarantined_rows,
        "quarantine_by_rule": totals,
        "rows_with_multiple_reasons": multi_reason,
        "per_month": per_month,
    }
    out = repo / "experiments" / "phase4_quarantine_reasons.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(repo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

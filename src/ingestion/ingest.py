"""Spark ingestion job: incremental + idempotent parquet -> Iceberg.

Usage (cluster): spark-submit with iceberg runtime package, passing
--input s3a://... --table catalog.ns.yellow_trips --contract contracts/yellow_trips.v1.yaml
Idempotency: rows carry (source_file, row_hash); writes use MERGE on that key
so replaying a file creates no duplicates (see tests/test_transforms.py).
"""

from __future__ import annotations

import argparse
import hashlib
import sys


def row_hash(values: list[str]) -> str:
    """Stable hash for idempotency keys."""
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:32]


def build_merge_sql(table: str, staging_view: str) -> str:
    """Return MERGE SQL making the load idempotent on (source_file, row_hash)."""
    return (
        f"MERGE INTO {table} t USING {staging_view} s "
        "ON t.source_file = s.source_file AND t.row_hash = s.row_hash "
        "WHEN NOT MATCHED THEN INSERT *"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Incremental parquet to Iceberg load")
    parser.add_argument("--input", required=True, help="Input parquet path (s3a:// or file://)")
    parser.add_argument("--table", required=True, help="Target Iceberg table (catalog.ns.table)")
    parser.add_argument("--contract", required=True, help="YAML contract path")
    parser.add_argument("--source-file", required=True, help="Source file label for idempotency")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point (Spark session wiring done in Phase 4)."""
    args = parse_args(argv)
    print(f"Would load {args.input} into {args.table} (contract {args.contract})")
    print(f"MERGE: {build_merge_sql(args.table, 'staging')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Data quality suites (Great Expectations wrapper, import-safe)."""

from __future__ import annotations

from typing import Any


def build_suite(table_name: str) -> dict[str, Any]:
    """Return a declarative expectation suite (rendered to GX in Phase 6)."""
    return {
        "suite_name": f"{table_name}_suite",
        "expectations": [
            {"type": "expect_column_values_to_not_be_null", "column": "tpep_pickup_datetime"},
            {"type": "expect_column_values_to_not_be_null", "column": "tpep_dropoff_datetime"},
            {"type": "expect_column_values_to_be_between", "column": "trip_distance", "min": 0},
            {"type": "expect_column_values_to_be_between", "column": "fare_amount", "min": 0},
            {"type": "expect_column_values_to_be_between", "column": "total_amount", "min": 0},
        ],
    }

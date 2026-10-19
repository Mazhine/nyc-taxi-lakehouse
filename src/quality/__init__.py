"""Data quality suites (Great Expectations wrapper, import-safe).

This module only *describes* the expectations as plain Python data. Great
Expectations is imported lazily by ``scripts/run-quality.py`` so that importing
this package (for example from a unit test or a CI lint) never requires the
heavy GX dependency.
"""

from __future__ import annotations

from typing import Any


def build_suite(table_name: str) -> dict[str, Any]:
    """Return a declarative expectation suite (rendered to GX in Phase 6).

    Five expectations cover the columns that matter most for analytics:
    timestamps must not be null and monetary/distance columns must be
    non-negative. The suite name is derived from the table so reports are
    self-describing.
    """
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

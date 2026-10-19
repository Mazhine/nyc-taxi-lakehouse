"""Quarantine logic: split rows into valid / quarantined with a reason.

This module is the *pure-Python reference implementation* of the row rules.
The Spark job re-implements the same logic as column expressions (because it
runs on distributed DataFrames), and the unit tests exercise this version so
the business rules are testable without a cluster. Keep the two in sync.
"""

from __future__ import annotations

from typing import Any


def _row_violations(row: dict[str, Any]) -> list[str]:
    """Return rule names violated by a row dict (pure-python, testable).

    De-duplicates the reasons with ``set`` and sorts them so the output is
    deterministic regardless of dictionary ordering.
    """
    reasons: list[str] = []
    pickup = row.get("tpep_pickup_datetime")
    dropoff = row.get("tpep_dropoff_datetime")
    if pickup is not None and dropoff is not None and pickup > dropoff:
        reasons.append("pickup_before_dropoff")
    for col in ("trip_distance", "fare_amount", "total_amount"):
        val = row.get(col)
        if val is not None and val < 0:
            reasons.append(f"{col}_non_negative")
    for col in ("PULocationID", "DOLocationID"):
        val = row.get(col)
        if val is not None and val <= 0:
            reasons.append("location_ids_positive")
            break
    for col in ("trip_distance", "PULocationID", "DOLocationID", "fare_amount", "total_amount"):
        if row.get(col) is None:
            reasons.append(f"{col}_not_null")
    return sorted(set(reasons))


def split_valid_quarantine(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows; quarantined rows get a ``_quarantine_reason`` field.

    Returns ``(valid, quarantined)``. Original rows are never mutated: a copy is
    made when adding the reason, so callers keep their input intact.
    """
    valid: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        reasons = _row_violations(row)
        if reasons:
            bad = dict(row)
            bad["_quarantine_reason"] = ";".join(reasons)
            quarantined.append(bad)
        else:
            valid.append(row)
    return valid, quarantined

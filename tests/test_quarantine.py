"""Quarantine tests: invalid rows get a reason, valid rows pass through."""

from datetime import datetime

from src.quarantine import split_valid_quarantine


def _good_row() -> dict:
    return {
        "tpep_pickup_datetime": datetime(2024, 1, 1, 10, 0, 0),
        "tpep_dropoff_datetime": datetime(2024, 1, 1, 10, 20, 0),
        "trip_distance": 2.5,
        "fare_amount": 12.0,
        "total_amount": 15.0,
        "PULocationID": 100,
        "DOLocationID": 200,
    }


def test_valid_row_passes():
    valid, quarantined = split_valid_quarantine([_good_row()])
    assert len(valid) == 1 and quarantined == []


def test_negative_fare_quarantined_with_reason():
    row = _good_row()
    row["fare_amount"] = -1.0
    valid, quarantined = split_valid_quarantine([row])
    assert valid == []
    assert len(quarantined) == 1
    assert "fare_amount_non_negative" in quarantined[0]["_quarantine_reason"]


def test_bad_times_and_zone_quarantined_not_lost():
    row = _good_row()
    row["tpep_pickup_datetime"] = datetime(2024, 1, 1, 11, 0, 0)
    row["tpep_dropoff_datetime"] = datetime(2024, 1, 1, 10, 0, 0)
    row["PULocationID"] = 0
    valid, quarantined = split_valid_quarantine([row])
    assert valid == []
    reason = quarantined[0]["_quarantine_reason"]
    assert "pickup_before_dropoff" in reason
    assert "location_ids_positive" in reason

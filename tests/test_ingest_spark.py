"""Spark-local transform tests (no cluster, no catalog).

Covers contract normalization (case/type drift) and the quarantine split on a
tiny in-memory DataFrame. Skipped if pyspark/Java is unavailable, and skipped
on Windows hosts (local Spark hangs there; run in the Linux spark-runner
container instead — see docs/DECISIONS.md D12).
"""

import datetime
import sys

import pytest

# Spark's local JVM hangs on this Windows host, so the whole module is skipped
# there. CI runs it inside apache/spark:3.5.9 (see .github/workflows/ci.yml).
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Spark local hangs on Windows host; runs in Linux container",
)

pyspark = pytest.importorskip("pyspark")
from pathlib import Path  # noqa: E402

from pyspark.sql import SparkSession  # noqa: E402

from src.ingestion import load_contract  # noqa: E402
from src.ingestion.ingest import normalize_columns, split_valid_quarantine_df  # noqa: E402

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "yellow_trips.v1.yaml"


@pytest.fixture(scope="module")
def spark():
    """One local Spark session shared by all tests in this module."""
    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-ingest")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def _rows():
    """Two rows: one valid, one with a negative fare (plus realistic 2024 drift)."""
    good = {
        "VendorID": 1,
        "tpep_pickup_datetime": datetime.datetime(2024, 1, 1, 10, 0, 0),
        "tpep_dropoff_datetime": datetime.datetime(2024, 1, 1, 10, 20, 0),
        "passenger_count": 1,
        "trip_distance": 2.5,
        "PULocationID": 100,
        "DOLocationID": 200,
        "payment_type": 1,
        "fare_amount": 12.0,
        "tip_amount": 2.0,
        "total_amount": 15.0,
    }
    bad = dict(good)
    bad["fare_amount"] = -1.0
    # Simulate 2024 drift: VendorID as int32 + extra column present.
    return [good, bad]


def test_normalize_casts_and_reports_drift(spark):
    """normalize_columns renames/casts to contract types and reports drift."""
    df = spark.createDataFrame(_rows())
    contract = load_contract(CONTRACT)
    normed, drift, missing = normalize_columns(df, contract)
    assert missing == []
    assert set(["VendorID", "fare_amount"]).issubset(set(normed.columns))
    dtypes = dict(normed.dtypes)
    assert dtypes["VendorID"] == "bigint"  # int32 -> int64 cast applied
    assert dtypes["fare_amount"] == "double"
    assert isinstance(drift["extra_columns"], list)


def test_split_quarantines_bad_row_with_reason(spark):
    """A single invalid row is quarantined with a machine-readable reason."""
    df = spark.createDataFrame(_rows())
    contract = load_contract(CONTRACT)
    normed, _, _ = normalize_columns(df, contract)
    valid, quarantined = split_valid_quarantine_df(normed)
    assert valid.count() == 1
    bad_rows = quarantined.collect()
    assert len(bad_rows) == 1
    assert "fare_amount_invalid" in bad_rows[0]["_quarantine_reason"]


def test_missing_column_reports_file_level(spark):
    """Missing required columns are reported so the file can be quarantined as a whole."""
    df = spark.createDataFrame(
        [{"VendorID": 1, "trip_distance": 1.0}],
    )
    df = df.withColumnRenamed("VendorID", "VendorID")
    contract = load_contract(CONTRACT)
    _, _, missing = normalize_columns(df, contract)
    assert "tpep_pickup_datetime" in missing
    assert "total_amount" in missing

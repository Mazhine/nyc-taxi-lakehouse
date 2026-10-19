"""Transform/idempotency tests (pure-python; Spark-local tests in test_ingest_spark).

Covers the two building blocks of the idempotency design: a deterministic row
hash and the file-level ledger decision. These run anywhere without Spark.
"""

from src.ingestion.ingest import build_merge_sql, row_hash, should_skip


def test_row_hash_stable_and_sized():
    """Same input -> same 32-char hash (deterministic, usable as a key)."""
    h1 = row_hash(["a", "b"])
    h2 = row_hash(["a", "b"])
    assert h1 == h2 and len(h1) == 32


def test_row_hash_differs_on_change():
    """Different input -> different hash (no collisions in practice)."""
    assert row_hash(["a"]) != row_hash(["b"])


def test_merge_sql_idempotent_on_source_file_and_hash():
    """The optional MERGE path keys on (source_file, row_hash) to avoid duplicates."""
    sql = build_merge_sql("cat.ns.yellow_trips", "staging")
    assert "source_file" in sql and "row_hash" in sql
    assert sql.strip().upper().startswith("MERGE INTO")


def test_ledger_skips_replay_but_loads_new_files():
    """The ledger skips a known file, loads a new one, and treats an empty table as new."""
    loaded = {"yellow_tripdata_2024-01"}
    assert should_skip(loaded, "yellow_tripdata_2024-01") is True
    assert should_skip(loaded, "yellow_tripdata_2024-02") is False
    assert should_skip(set(), "yellow_tripdata_2024-01") is False

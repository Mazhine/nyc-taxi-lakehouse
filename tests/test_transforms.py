"""Transform/idempotency tests (pure-python; Spark-local tests land in Phase 4)."""

from src.ingestion.ingest import build_merge_sql, row_hash


def test_row_hash_stable_and_sized():
    h1 = row_hash(["a", "b"])
    h2 = row_hash(["a", "b"])
    assert h1 == h2 and len(h1) == 32


def test_row_hash_differs_on_change():
    assert row_hash(["a"]) != row_hash(["b"])


def test_merge_sql_idempotent_on_source_file_and_hash():
    sql = build_merge_sql("cat.ns.yellow_trips", "staging")
    assert "source_file" in sql and "row_hash" in sql
    assert sql.strip().upper().startswith("MERGE INTO")

"""Iceberg maintenance SQL builders (compaction, snapshots)."""

from __future__ import annotations


def rewrite_data_files_sql(
    table: str, strategy: str = "sort", sort_order: str = "tpep_pickup_datetime"
) -> str:
    """Return CALL statement compacting small files (Spark SQL)."""
    if strategy == "sort":
        return (
            f"CALL catalog.system.rewrite_data_files(table => '{table}', "
            f"strategy => 'sort', sort_order => '{sort_order}')"
        )
    return f"CALL catalog.system.rewrite_data_files(table => '{table}', strategy => 'binpack')"


def expire_snapshots_sql(table: str, retain_last: int = 5) -> str:
    """Return CALL statement expiring old snapshots, keeping N latest."""
    return f"CALL catalog.system.expire_snapshots(table => '{table}', retain_last => {retain_last})"

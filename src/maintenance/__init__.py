"""Iceberg maintenance SQL builders (compaction, snapshots).

These helpers only *build SQL strings*; they never talk to a cluster. The
benchmark script (``scripts/bench-iceberg.py``) executes them through Trino or
Spark. Keeping them as pure functions makes the exact maintenance commands
reviewable and testable.
"""

from __future__ import annotations


def rewrite_data_files_sql(
    table: str, strategy: str = "sort", sort_order: str = "tpep_pickup_datetime"
) -> str:
    """Return CALL statement compacting small files (Spark SQL).

    ``sort`` rewrites files sorted by ``sort_order`` (better for range filters),
    ``binpack`` only merges small files (cheaper, no data reordering).
    """
    if strategy == "sort":
        return (
            f"CALL catalog.system.rewrite_data_files(table => '{table}', "
            f"strategy => 'sort', sort_order => '{sort_order}')"
        )
    return f"CALL catalog.system.rewrite_data_files(table => '{table}', strategy => 'binpack')"


def expire_snapshots_sql(table: str, retain_last: int = 5) -> str:
    """Return CALL statement expiring old snapshots, keeping N latest."""
    return f"CALL catalog.system.expire_snapshots(table => '{table}', retain_last => {retain_last})"

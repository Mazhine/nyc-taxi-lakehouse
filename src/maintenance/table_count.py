"""Count rows (and per-source rows) of an Iceberg table via REST catalog.

A tiny verification helper used right after a load to prove the ledger worked:
the total should equal the sum of the monthly ``valid_rows`` and each
``source_file`` should appear exactly once. It runs on K8s (spark-runner image,
``--master local[*]``) or on any host with Spark.
"""

from __future__ import annotations

import argparse
import json
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser(description="Count Iceberg table rows")
    p.add_argument("--table", required=True)
    p.add_argument("--catalog-uri", default="http://localhost:8181/catalog")
    p.add_argument("--warehouse", default="warehouse")
    p.add_argument("--s3-endpoint", default="http://localhost:9000")
    p.add_argument("--master", default="local[*]")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Print a JSON summary with the total and per-source counts."""
    from pyspark.sql import SparkSession

    args = parse_args(argv)
    spark = (
        SparkSession.builder.master(args.master)
        .appName("table-count")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        # Iceberg vectorized reads SIGSEGV on this JVM/JDK combination (D14).
        .config("spark.sql.iceberg.vectorization.enabled", "false")
        .config("spark.sql.catalog.lakekeeper", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.lakekeeper.type", "rest")
        .config("spark.sql.catalog.lakekeeper.uri", args.catalog_uri)
        .config("spark.sql.catalog.lakekeeper.warehouse", args.warehouse)
        .config("spark.sql.catalog.lakekeeper.token", "dummy")
        .config("spark.sql.catalog.lakekeeper.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.lakekeeper.s3.endpoint", args.s3_endpoint)
        .config("spark.sql.catalog.lakekeeper.s3.path-style-access", "true")
        .config("spark.sql.catalog.lakekeeper.s3.access-key-id", "minioadmin")
        .config("spark.sql.catalog.lakekeeper.s3.secret-access-key", "minioadmin-local-demo-only")
        .getOrCreate()
    )
    try:
        total = spark.sql(f"SELECT COUNT(*) AS n FROM {args.table}").collect()[0]["n"]
        by_src = spark.sql(
            f"SELECT source_file, COUNT(*) AS n FROM {args.table} "
            "GROUP BY source_file ORDER BY source_file"
        ).collect()
        print(
            json.dumps(
                {
                    "table": args.table,
                    "total": total,
                    "by_source": [{r["source_file"]: r["n"]} for r in by_src],
                },
                indent=2,
            ),
            flush=True,
        )
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())

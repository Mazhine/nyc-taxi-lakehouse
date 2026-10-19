"""Load ``taxi_zone_lookup.csv`` into ``nyc.taxi_zones`` (create-then-append, idempotent).

The zone lookup is a small *reference / dimension* table (265 rows) used by
``sql/05_zone_names.sql`` to translate numeric ``PULocationID`` values into
human-readable zone and borough names. It is loaded once (not per month).

Runs on Kubernetes via ``scripts/load-zones.ps1`` (a Job in the spark-jobs
chart) or locally with any Spark equipped with the Lakekeeper REST catalog.
"""

from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args (defaults target the local kind/Docker setup)."""
    p = argparse.ArgumentParser(description="Load taxi zones reference table")
    p.add_argument("--input", default="s3a://lakehouse/raw/taxi_zone_lookup.csv")
    p.add_argument("--table", default="lakekeeper.nyc.taxi_zones")
    p.add_argument("--catalog-uri", default="http://localhost:8181/catalog")
    p.add_argument("--warehouse", default="warehouse")
    p.add_argument("--s3-endpoint", default="http://localhost:9000")
    p.add_argument("--master", default="local[*]")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Create the table once, then append only when empty (immutable reference)."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    args = parse_args(argv)
    # Same catalog + S3 wiring as ingest.py: the Iceberg REST catalog for table
    # operations and plain Hadoop S3A for reading the raw CSV.
    spark = (
        SparkSession.builder.master(args.master)
        .appName("load-zones")
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
        .config("spark.hadoop.fs.s3a.endpoint", args.s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin-local-demo-only")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )
    try:
        # Idempotency: the reference table is immutable, so if it exists we stop.
        if spark.catalog.tableExists(args.table):
            n = spark.table(args.table).count()
            print(f"zones table exists with {n} rows: skip", flush=True)
            return 0
        # Read the CSV with a header, rename LocationID to snake_case and cast
        # to bigint so it joins cleanly with the trips fact table.
        df = spark.read.option("header", "true").csv(args.input)
        df = df.withColumnRenamed("LocationID", "location_id").withColumn(
            "location_id", F.col("location_id").cast("bigint")
        )
        df.writeTo(args.table).create()
        print(f"zones table created with {df.count()} rows", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())

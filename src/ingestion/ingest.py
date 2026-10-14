"""Spark ingestion job: incremental + idempotent parquet -> Iceberg.

Contract-driven: schema drift (renames/case/type changes) is normalized and
logged; missing required columns quarantine the whole file; rows violating
rules go to quarantine with a reason. Writes use MERGE on
(source_file, row_hash), so replaying a file creates no duplicates.

Local example:
  python src/ingestion/ingest.py --input data/yellow_tripdata_2024-01.parquet \\
    --table lakekeeper.nyc.yellow_trips --contract contracts/yellow_trips.v1.yaml \\
    --source-file yellow_tripdata_2024-01 --s3-endpoint http://localhost:9000 \\
    --catalog-uri http://localhost:8181/catalog --limit 10000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

CANONICAL_ORDER = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount",
]
HASH_COLUMNS = CANONICAL_ORDER

PACKAGES = ",".join(
    [
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1",
        "org.apache.iceberg:iceberg-aws-bundle:1.6.1",
        "org.apache.hadoop:hadoop-aws:3.3.4",
        "com.amazonaws:aws-java-sdk-bundle:1.12.262",
    ]
)


def row_hash(values: list[str]) -> str:
    """Stable hash for idempotency keys."""
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:32]


def build_merge_sql(table: str, staging_view: str) -> str:
    """Return MERGE SQL making the load idempotent on (source_file, row_hash)."""
    return (
        f"MERGE INTO {table} t USING {staging_view} s "
        "ON t.source_file = s.source_file AND t.row_hash = s.row_hash "
        "WHEN NOT MATCHED THEN INSERT *"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser(description="Incremental parquet to Iceberg load")
    p.add_argument("--input", required=True, help="Parquet path (file://, s3a://)")
    p.add_argument("--table", required=True, help="Target table (catalog.ns.table)")
    p.add_argument("--contract", required=True, help="YAML contract path")
    p.add_argument("--source-file", required=True, help="Source label for idempotency")
    p.add_argument("--quarantine-path", default=None, help="Quarantine output dir")
    p.add_argument("--catalog-uri", default="http://localhost:8181/catalog")
    p.add_argument("--warehouse", default="warehouse")
    p.add_argument("--s3-endpoint", default="http://localhost:9000")
    p.add_argument("--s3-access-key", default=os.environ.get("S3_ACCESS_KEY", "minioadmin"))
    p.add_argument(
        "--s3-secret-key", default=os.environ.get("S3_SECRET_KEY", "minioadmin-local-demo-only")
    )
    p.add_argument("--master", default="local[*]")
    p.add_argument("--limit", type=int, default=None, help="Cap input rows (tests/demos)")
    return p.parse_args(argv)


def build_spark(args: argparse.Namespace):
    """Build a Spark session wired to Lakekeeper REST + S3A/MinIO."""
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.master(args.master)
        .appName(f"ingest-{args.source_file}")
        .config("spark.jars.packages", PACKAGES)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.iceberg.vectorization.enabled", "false")
        .config("spark.sql.catalog.lakekeeper", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.lakekeeper.type", "rest")
        .config("spark.sql.catalog.lakekeeper.uri", args.catalog_uri)
        .config("spark.sql.catalog.lakekeeper.warehouse", args.warehouse)
        .config("spark.sql.catalog.lakekeeper.token", "dummy")
        .config("spark.sql.catalog.lakekeeper.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.lakekeeper.s3.endpoint", args.s3_endpoint)
        .config("spark.sql.catalog.lakekeeper.s3.path-style-access", "true")
        .config("spark.sql.catalog.lakekeeper.s3.access-key-id", args.s3_access_key)
        .config("spark.sql.catalog.lakekeeper.s3.secret-access-key", args.s3_secret_key)
        .config("spark.hadoop.fs.s3a.endpoint", args.s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", args.s3_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", args.s3_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def normalize_columns(df, contract):
    """Rename case-insensitively + cast to contract types; return (df, drift)."""
    from pyspark.sql import functions as F

    required = [c["name"] for c in contract["required_columns"]]
    type_map = {c["name"]: c["type"] for c in contract["required_columns"]}
    actual = df.columns
    by_lower = {c.lower(): c for c in actual}
    drift = {
        "extra_columns": [c for c in actual if c.lower() not in {r.lower() for r in required}],
        "renamed_or_case_changed": [
            {"contract": r, "actual": by_lower[r.lower()]}
            for r in required
            if r.lower() in by_lower and by_lower[r.lower()] != r
        ],
    }
    missing = [r for r in required if r.lower() not in by_lower]
    for req in required:
        if req.lower() not in by_lower:
            continue
        src_col = by_lower[req.lower()]
        target = type_map[req]
        if "timestamp" in target:
            df = df.withColumn(req, F.to_timestamp(F.col(f"`{src_col}`")))
        elif target == "int64":
            df = df.withColumn(req, F.col(f"`{src_col}`").cast("bigint"))
        elif target == "double":
            df = df.withColumn(req, F.col(f"`{src_col}`").cast("double"))
        elif src_col != req:
            df = df.withColumnRenamed(src_col, req)
        if src_col != req and src_col in df.columns:
            df = df.drop(src_col)
    return df.select(*[r for r in required if r.lower() in by_lower]), drift, missing


def split_valid_quarantine_df(df):
    """Split a normalized DataFrame; quarantine rows get _quarantine_reason."""
    from pyspark.sql import functions as F

    bad = (
        (F.col("tpep_pickup_datetime") > F.col("tpep_dropoff_datetime"))
        | (F.col("trip_distance") < 0)
        | (F.col("fare_amount") < 0)
        | (F.col("total_amount") < 0)
        | (F.col("PULocationID") <= 0)
        | (F.col("DOLocationID") <= 0)
        | F.col("trip_distance").isNull()
        | F.col("fare_amount").isNull()
        | F.col("total_amount").isNull()
        | F.col("PULocationID").isNull()
        | F.col("DOLocationID").isNull()
    )
    reasons = F.concat_ws(
        ";",
        F.when(
            F.col("tpep_pickup_datetime") > F.col("tpep_dropoff_datetime"), "pickup_before_dropoff"
        ),
        F.when(
            (F.col("trip_distance") < 0) | F.col("trip_distance").isNull(), "trip_distance_invalid"
        ),
        F.when((F.col("fare_amount") < 0) | F.col("fare_amount").isNull(), "fare_amount_invalid"),
        F.when(
            (F.col("total_amount") < 0) | F.col("total_amount").isNull(), "total_amount_invalid"
        ),
        F.when(
            (F.col("PULocationID") <= 0) | F.col("PULocationID").isNull(), "location_ids_invalid"
        ),
        F.when(
            (F.col("DOLocationID") <= 0) | F.col("DOLocationID").isNull(), "location_ids_invalid"
        ),
    )
    return df.filter(~bad), df.filter(bad).withColumn("_quarantine_reason", reasons)


def should_skip(loaded_files: set[str], source_file: str) -> bool:
    """Return True when this source file was already loaded (idempotency ledger)."""
    return source_file in loaded_files


def loaded_source_files(spark, table: str) -> set[str]:
    """Return DISTINCT source_file values already in the table (narrow scan)."""
    try:
        rows = spark.sql(f"SELECT DISTINCT source_file FROM {table}").collect()
        return {r["source_file"] for r in rows if r["source_file"]}
    except Exception:
        return set()


def run(args: argparse.Namespace) -> dict:
    """Run the load; return a JSON-serializable summary."""
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from pyspark.sql import functions as F

    from src.ingestion import load_contract

    contract = load_contract(args.contract)

    spark = build_spark(args)
    try:
        if should_skip(loaded_source_files(spark, args.table), args.source_file):
            return {
                "source_file": args.source_file,
                "input_rows": 0,
                "valid_rows": 0,
                "quarantined_rows": 0,
                "status": "skipped_already_loaded",
                "drift": {},
            }
        df = spark.read.parquet(args.input)
        if args.limit:
            df = df.limit(args.limit)
        input_rows = df.count()

        df, drift, missing = normalize_columns(df, contract)
        if missing:
            summary = {
                "source_file": args.source_file,
                "input_rows": input_rows,
                "status": "file_quarantined",
                "reason": f"missing_columns: {missing}",
                "drift": drift,
            }
            if args.quarantine_path:
                (
                    df.withColumn(
                        "_quarantine_reason", F.lit(f"missing_columns: {','.join(missing)}")
                    )
                    .withColumn("source_file", F.lit(args.source_file))
                    .write.mode("append")
                    .parquet(f"{args.quarantine_path}/source_file={args.source_file}")
                )
                summary["quarantine_path"] = args.quarantine_path
            return summary

        # Normalize: case-insensitive rename + safe casts to contract types.
        df = df.withColumn("source_file", F.lit(args.source_file))
        concat_cols = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in HASH_COLUMNS]
        df = df.withColumn("row_hash", F.sha2(F.concat_ws("|", *concat_cols), 256).substr(1, 32))

        valid, quarantined = split_valid_quarantine_df(df)
        n_valid = valid.count()
        n_quar = quarantined.count()

        if args.quarantine_path and n_quar:
            (
                quarantined.write.mode("append").parquet(
                    f"{args.quarantine_path}/source_file={args.source_file}"
                )
            )

        table_cols = [f.name for f in spark.table(args.table).schema.fields]
        valid.select(*table_cols).writeTo(args.table).append()
        return {
            "source_file": args.source_file,
            "input_rows": input_rows,
            "valid_rows": n_valid,
            "quarantined_rows": n_quar,
            "status": "appended",
            "drift": drift,
        }
    finally:
        spark.stop()


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

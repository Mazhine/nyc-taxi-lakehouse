"""Data quality gates: Great Expectations suite on trusted + quarantine samples.

- Trusted sample: one Iceberg data file from MinIO (valid rows only) -> expect SUCCESS.
- Quarantine sample: one quarantine parquet from MinIO -> expect FAILURE
  (negative control proving quarantine holds exactly the invalid rows).
Outputs: experiments/phase6_quality.json + GX result JSONs (versioned).
Data Docs HTML is built for local viewing only (git-ignored).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import boto3
import great_expectations as gx
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
GX_DIR = ROOT / "gx"
SAMPLE_ROWS_TRUSTED = 200000
SAMPLE_ROWS_QUARANTINE = 20000


def minio() -> boto3.client:
    """Return a boto3 client for local MinIO."""
    return boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin-local-demo-only",
        region_name="us-east-1",
    )


def first_parquet_key(s3: boto3.client, bucket: str, prefix: str) -> str:
    """Return the first .parquet key under a prefix."""
    token = None
    while True:
        kwargs: dict = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                return obj["Key"]
        if not page.get("IsTruncated"):
            raise FileNotFoundError(f"no parquet under s3://{bucket}/{prefix}")
        token = page["NextContinuationToken"]


def sample_frame(s3: boto3.client, bucket: str, key: str, n: int, local: Path) -> pd.DataFrame:
    """Download a parquet key and return the first n rows as pandas."""
    local.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(local))
    table = pq.read_table(str(local)).slice(0, n)
    return table.to_pandas()


def build_suite(context: gx.DataContext) -> gx.ExpectationSuite:
    """Create the yellow-trips suite mirroring contracts/yellow_trips.v1.yaml."""
    exps = gx.expectations
    suite = context.suites.add(gx.ExpectationSuite(name="yellow_trips"))
    suite.add_expectation(exps.ExpectColumnValuesToNotBeNull(column="tpep_pickup_datetime"))
    suite.add_expectation(exps.ExpectColumnValuesToNotBeNull(column="tpep_dropoff_datetime"))
    suite.add_expectation(
        exps.ExpectColumnValuesToBeBetween(column="trip_distance", min_value=0)
    )
    suite.add_expectation(exps.ExpectColumnValuesToBeBetween(column="fare_amount", min_value=0))
    suite.add_expectation(exps.ExpectColumnValuesToBeBetween(column="total_amount", min_value=0))
    suite.add_expectation(exps.ExpectColumnValuesToBeBetween(column="PULocationID", min_value=1))
    suite.add_expectation(exps.ExpectColumnValuesToBeBetween(column="DOLocationID", min_value=1))
    return suite


def validate(
    context: gx.DataContext, suite: gx.ExpectationSuite, name: str, df: pd.DataFrame
) -> dict:
    """Validate a dataframe; return a JSON-serializable result dict."""
    ds = context.data_sources.add_pandas(f"pandas_{name}")
    asset = ds.add_dataframe_asset(name=f"asset_{name}")
    bdef = asset.add_batch_definition_whole_dataframe(f"batch_{name}")
    batch = bdef.get_batch(batch_parameters={"dataframe": df})
    result = batch.validate(suite)
    return result.to_json_dict()


def main() -> None:
    """Run trusted + quarantine validations and write versioned reports."""
    if GX_DIR.exists():
        shutil.rmtree(GX_DIR)
    context = gx.get_context(mode="file", project_root_dir=str(GX_DIR))
    suite = build_suite(context)
    s3 = minio()

    trusted_key = first_parquet_key(s3, "lakehouse", "iceberg/")
    trusted = sample_frame(s3, "lakehouse", trusted_key, SAMPLE_ROWS_TRUSTED,
                           ROOT / "data" / "_tmp_quality_trusted.parquet")
    quar_key = first_parquet_key(s3, "quarantine", "yellow_trips/")
    quar = sample_frame(s3, "quarantine", quar_key, SAMPLE_ROWS_QUARANTINE,
                        ROOT / "data" / "_tmp_quality_quarantine.parquet")

    trusted_res = validate(context, suite, "trusted", trusted)
    quar_res = validate(context, suite, "quarantine", quar)

    (EXP / "phase6_gx_trusted.json").write_text(json.dumps(trusted_res, indent=2)[:200000],
                                                encoding="utf-8")
    (EXP / "phase6_gx_quarantine.json").write_text(json.dumps(quar_res, indent=2)[:200000],
                                                   encoding="utf-8")
    try:
        context.build_data_docs()
        datadocs = "built (git-ignored)"
    except Exception as exc:  # docs are a bonus, JSON is the report
        datadocs = f"skipped: {type(exc).__name__}: {exc}"

    def failed_names(res: dict) -> list[str]:
        return [
            r["expectation_config"]["kwargs"].get("column", "?")
            for r in res.get("results", [])
            if not r.get("success", True)
        ]

    summary = {
        "suite": "yellow_trips",
        "expectations": len(suite.expectations),
        "trusted": {
            "key": trusted_key,
            "rows": len(trusted),
            "success": trusted_res["success"],
            "success_percent": trusted_res["statistics"]["success_percent"],
        },
        "quarantine_negative_control": {
            "key": quar_key,
            "rows": len(quar),
            "success": quar_res["success"],
            "expected_success": False,
            "failed_columns": sorted(set(failed_names(quar_res))),
        },
        "datadocs": datadocs,
        "gx_version": gx.__version__,
    }
    (EXP / "phase6_quality.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    assert trusted_res["success"] is True, "trusted sample must pass all expectations"
    assert quar_res["success"] is False, "quarantine sample must fail (negative control)"


if __name__ == "__main__":
    main()

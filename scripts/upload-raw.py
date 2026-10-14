"""Upload local TLC parquet files to MinIO raw/ prefix (host -> localhost:9000)."""

from __future__ import annotations

from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://localhost:9000"
BUCKET = "lakehouse"
PREFIX = "raw/"


def main() -> None:
    """Upload data/*.parquet to s3://lakehouse/raw/ (skip if same size exists)."""
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin-local-demo-only",
        region_name="us-east-1",
    )
    for local in sorted((ROOT / "data").glob("yellow_tripdata_*.parquet")):
        key = PREFIX + local.name
        try:
            head = s3.head_object(Bucket=BUCKET, Key=key)
            if head["ContentLength"] == local.stat().st_size:
                print(f"exists: {key}")
                continue
        except Exception:
            pass
        print(f"uploading {local.name} ({local.stat().st_size / 1e6:.0f} MB) ...")
        s3.upload_file(str(local), BUCKET, key)
    print("done.")


if __name__ == "__main__":
    main()

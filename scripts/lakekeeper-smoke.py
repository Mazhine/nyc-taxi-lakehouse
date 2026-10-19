"""Phase 3 smoke test: create namespace + table via Lakekeeper REST (PyIceberg).

Proves the catalog + MinIO wiring end-to-end *without* Spark: if PyIceberg can
create a table through the REST catalog and get back an ``s3://`` location, the
catalog and object store are correctly connected. The table is created empty
here; Phase 4 fills it with Spark. Output -> ``experiments/phase3_catalog.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import DoubleType, LongType, NestedField, StringType, TimestampType

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
CATALOG_URI = "http://localhost:8181/catalog"
WAREHOUSE = "warehouse"
NAMESPACE = "nyc"
TABLE = "yellow_trips"


def main() -> None:
    """Create namespace/table if missing, record proof JSON."""
    catalog = RestCatalog(
        name="lakekeeper",
        uri=CATALOG_URI,
        warehouse=WAREHOUSE,
        token="dummy",  # unsecured local deployment only
    )
    # Idempotent: create the namespace only if it is not already there.
    existing = [ns for ns in catalog.list_namespaces()]
    if (NAMESPACE,) not in existing:
        catalog.create_namespace(NAMESPACE)
    # The canonical schema: 11 trip columns + 2 pipeline columns (source_file,
    # row_hash). Field ids are explicit because Iceberg tracks columns by id.
    schema = Schema(
        NestedField(1, "VendorID", LongType(), required=False),
        NestedField(2, "tpep_pickup_datetime", TimestampType(), required=True),
        NestedField(3, "tpep_dropoff_datetime", TimestampType(), required=True),
        NestedField(4, "passenger_count", LongType(), required=False),
        NestedField(5, "trip_distance", DoubleType(), required=True),
        NestedField(6, "PULocationID", LongType(), required=True),
        NestedField(7, "DOLocationID", LongType(), required=True),
        NestedField(8, "payment_type", LongType(), required=False),
        NestedField(9, "fare_amount", DoubleType(), required=True),
        NestedField(10, "tip_amount", DoubleType(), required=False),
        NestedField(11, "total_amount", DoubleType(), required=True),
        NestedField(12, "source_file", StringType(), required=False),
        NestedField(13, "row_hash", StringType(), required=False),
    )
    table_id = f"{NAMESPACE}.{TABLE}"
    try:
        tbl = catalog.create_table(table_id, schema=schema)
        created = True
    except Exception as exc:  # already exists -> load it
        tbl = catalog.load_table(table_id)
        created = False
        print(f"table exists, loaded ({type(exc).__name__})")
    proof = {
        "catalog_uri": CATALOG_URI,
        "warehouse": WAREHOUSE,
        "namespaces": [list(ns) for ns in catalog.list_namespaces()],
        "tables_in_nyc": [t for t in catalog.list_tables(NAMESPACE)],
        "table_location": tbl.location(),
        "table_schema": str(tbl.schema()),
        "created_now": created,
        "pyiceberg_version": "0.12.0",
    }
    out = EXP / "phase3_catalog.json"
    out.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps(proof, indent=2)[:1500])


if __name__ == "__main__":
    main()

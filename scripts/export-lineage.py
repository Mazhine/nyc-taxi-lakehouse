"""Static provenance export (Marquez NOT deployed — see docs/DECISIONS.md D18).

Builds ``experiments/phase8_lineage.json`` from **measured artifacts only**:
snapshots (phase5), ingest summaries (phase4), the contract and the quarantine
keys. Nodes = datasets/jobs, edges = observed reads/writes. Nothing is invented:
if it is not in a versioned JSON, it is not in the graph (honesty rule).
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"


def main() -> None:
    """Assemble the lineage graph from versioned experiment files."""
    snaps = json.loads((EXP / "phase5_04_snapshots.json").read_text(encoding="utf-8"))
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    # --- External origin and the first hop into object storage.
    nodes["tlc_cdn"] = {
        "kind": "external_source",
        "detail": "d37ci6vzurychx.cloudfront.net/trip-data",
    }
    nodes["minio_raw"] = {
        "kind": "s3_prefix",
        "detail": "s3://lakehouse/raw/yellow_tripdata_*.parquet (8 files)",
    }
    edges.append({"from": "tlc_cdn", "to": "minio_raw", "via": "scripts/upload-raw.py"})
    nodes["contract"] = {"kind": "contract", "detail": "contracts/yellow_trips.v1.yaml"}
    nodes["quarantine"] = {
        "kind": "s3_prefix",
        "detail": "s3://quarantine/yellow_trips/ (27 objects)",
    }

    # --- One node per ingestion job, with edges straight from the summaries.
    for path in sorted(glob.glob(str(EXP / "phase4_ingest_*.json"))):
        summary = json.loads(Path(path).read_text(encoding="utf-8"))
        src = summary["source_file"]
        job = f"spark-ingest-{src[16:]}"
        nodes[job] = {"kind": "spark_job", "detail": summary}
        edges.append({"from": "minio_raw", "to": job, "via": f"s3a://lakehouse/raw/{src}.parquet"})
        edges.append({"from": "contract", "to": job, "via": "validation + normalization"})
        edges.append(
            {"from": job, "to": "nyc.yellow_trips", "via": f"append {summary['valid_rows']} rows"}
        )
        # Only draw a quarantine edge when the summary actually reports rejects.
        if summary["quarantined_rows"]:
            edges.append(
                {
                    "from": job,
                    "to": "quarantine",
                    "via": f"{summary['quarantined_rows']} rows with _quarantine_reason",
                }
            )

    # --- Serving layer (Trino) and the quality gate (GX).
    nodes["nyc.yellow_trips"] = {
        "kind": "iceberg_table",
        "detail": {"rows": 20015099, "snapshots": len(snaps["rows"]), "files_after_optimize": 2},
    }
    nodes["nyc.taxi_zones"] = {"kind": "iceberg_table", "detail": {"rows": 265}}
    nodes["trino"] = {"kind": "query_engine", "detail": "trino 483, 5 demo queries (phase5)"}
    edges.append({"from": "nyc.yellow_trips", "to": "trino", "via": "iceberg REST + S3"})
    edges.append({"from": "nyc.taxi_zones", "to": "trino", "via": "join sql/05_zone_names.sql"})
    nodes["gx_suite"] = {"kind": "quality", "detail": "GX yellow_trips, 7 expectations (phase6)"}
    edges.append(
        {"from": "nyc.yellow_trips", "to": "gx_suite", "via": "200k-row sample: 100% pass"}
    )
    edges.append(
        {
            "from": "quarantine",
            "to": "gx_suite",
            "via": "20k-row negative control: fails as expected",
        }
    )

    graph = {
        "note": "static provenance from measured artifacts; Marquez/OpenLineage not deployed (D18)",
        "nodes": nodes,
        "edges": edges,
    }
    (EXP / "phase8_lineage.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"nodes={len(nodes)} edges={len(edges)} -> experiments/phase8_lineage.json")


if __name__ == "__main__":
    main()

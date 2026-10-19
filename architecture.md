# Architecture

This document explains how the pieces fit together and why. For the exact
version pins and trade-offs, see `README.md` and `docs/DECISIONS.md`.

## Big picture

```
                         (public CDN)
   NYC TLC parquet  ───────────────▶  scripts/download-data.ps1
                                              │
                                              ▼
                                   data/  (git-ignored, ~500 MB)
                                              │
                              scripts/upload-raw.py  (boto3 → S3)
                                              ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │ kind cluster (Terraform)            namespace: lakehouse            │
   │                                                                    │
   │   MinIO  ── s3://lakehouse/raw/  ──▶  Spark Job (ingest.py)        │
   │     │                                   │        │                  │
   │     │                         valid rows│        │invalid rows      │
   │     │                                   ▼        ▼                 │
   │     │                        Lakekeeper catalog  s3://quarantine/   │
   │     │                                   │                          │
   │     └──────── Iceberg data files ◀──────┘                          │
   │                       │                                            │
   │                       ▼                                            │
   │                   Trino 483  ──▶  SQL / notebooks (sql/*.sql)      │
   └────────────────────────────────────────────────────────────────────┘
```

## Components and responsibilities

| Component | Runs as | Responsibility |
|---|---|---|
| **kind cluster** | Docker containers | The single-node Kubernetes the whole platform lives on. Created by Terraform. |
| **MinIO** | Deployment + PVC | S3-compatible store: raw uploads, Iceberg data/metadata, quarantine zone. |
| **PostgreSQL** | Deployment + PVC | Catalog metadata only (no trip data). Used by Lakekeeper. |
| **Lakekeeper** | Deployment + migrate/bootstrap Jobs | Iceberg REST catalog: the shared "table registry" for Spark and Trino. |
| **Spark jobs** | `spark-jobs` Helm chart Jobs | `ingest.py` (monthly validation + append) and `load_zones.py` (reference table). Executors are separate pods; RBAC for `spark` ServiceAccount lives in `rbac.yaml`. |
| **Trino** | Official chart (1 coord + 1 worker) | SQL query engine over the Iceberg tables via REST catalog. |
| **Argo CD** | Deployment | GitOps control plane; app-of-apps manifests under `infra/argocd/`. |
| **Great Expectations** | Host Python | Quality suites over the trusted table + quarantine negative control. |

## Data flow and layer names

The layers are deliberately named `raw → validated → trusted` (not Medallion):

1. **raw** — the original parquet/CSV files land in `s3://lakehouse/raw/`
   unchanged. This is the immutable replay source.
2. **validated** — `ingest.py` reads one month, normalizes column-name/type
   drift (e.g. `airport_fee` → `Airport_fee`) and evaluates the contract rules.
3. **trusted** — rows passing every rule are appended to the Iceberg table
   `lakekeeper.nyc.yellow_trips`. Rows failing any rule go to
   `s3://quarantine/yellow_trips/` with a `_quarantine_reason`.

## Why incremental + a file ledger

Loading 20 M rows with `MERGE INTO` OOMs this single node (D13). Instead, each
ingest records the source files it has already processed in a ledger; a replay
sees them and exits with `skipped_already_loaded` and adds **zero** files. This
keeps ingestion idempotent without a heavy upsert.

## Kubernetes wiring details

- **Client mode:** the driver runs in the submitter pod. Because no Service/DNS
  entry exists for it, the job advertises `spark.driver.host=$(hostname -i)` so
  executors can call back.
- **Images:** `lakehouse/spark-runner:3.5.9-0.1.0` bakes Spark 3.5.9 + JRE 17 +
  the Iceberg and S3A jars, plus the job sources at `/opt/spark/jobs/`.
- **RBAC:** the `spark` ServiceAccount may create/delete/patch pods, services,
  configmaps and PVCs in `lakehouse`.
- **Workaround:** Iceberg's vectorized/Arrow reader segfaults this JVM under
  WSL2/Docker, so jobs run with `spark.sql.iceberg.vectorization.enabled=false`
  (D14).

## Reproducibility contract

`scripts/up.ps1` performs seven idempotent steps (cluster, Argo CD, MinIO,
Postgres, Lakekeeper, Trino, Spark image). `scripts/verify.ps1` then asserts
that the trusted row count equals the sum of the per-month valid rows, that
per-month counts match, and that snapshot totals are consistent — see
`experiments/phase10_verify.txt` for a real 8/8 PASS run.

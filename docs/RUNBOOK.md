# RUNBOOK

## 0. One-time machine setup (Windows 11 + PowerShell)

- Install Docker Desktop (WSL2 backend) and start it: `docker info` must work.
- Install tools (winget, versions in README): `Helm.Helm 4.3.0`,
  `Hashicorp.Terraform 1.16.5`, `Kubernetes.kind 0.33.0`,
  `EclipseAdoptium.Temurin.17.JDK`, Python 3.12. Reopen the shell after winget
  installs so PATH picks them up (scripts also refresh PATH themselves).
- Cap WSL2 so Windows keeps breathing (project Phase 0 created this):
  `~/.wslconfig` with `memory=20GB`, `processors=8`, `swap=4GB`.
- Python env: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r
  requirements.txt` (pinned; Spark runs in-cluster, host Spark is not required).
- Credentials are demo-local and fixed in the chart values. To use other
  values, pass `--set` to the corresponding `helm` command; there is no `.env`.

## 1. Start (one command)

```powershell
.\scripts\download-data.ps1   # first time only (~500 MB into data/)
.\scripts\up.ps1              # kind + Argo CD + MinIO + Postgres + Lakekeeper + Trino
```

`up.ps1` does: `terraform init/validate/apply` → helm repos → Argo CD 3.5.5 →
MinIO/postgres/Lakekeeper charts (+ migrate/bootstrap/warehouse Jobs) →
Trino chart → waits + smoke logs.

## 2. Load data

```powershell
.\.venv\Scripts\python.exe scripts\upload-raw.py     # data/*.parquet + zone CSV -> s3://lakehouse/raw/
.\scripts\run-ingest.ps1 2024-01                    # positional month arg; repeat 02..06
.\scripts\load-zones.ps1                            # reference table (idempotent)
```

Each Job validates against `contracts/yellow_trips.v1.yaml`, appends valid
rows to `lakekeeper.nyc.yellow_trips`, writes invalid rows to
`s3://quarantine/yellow_trips/` with `_quarantine_reason`.
Re-running a month is a no-op (`skipped_already_loaded`).
`load-zones.ps1` loads `taxi_zone_lookup.csv` into `lakekeeper.nyc.taxi_zones`
(265 rows; skips when the table already exists).

## 3. Query / quality / benchmarks

```powershell
.\scripts\verify.ps1                                  # acceptance check (read-only)
.\.venv\Scripts\python.exe scripts\trino-query.py     # Trino on localhost:8080
.\.venv\Scripts\python.exe scripts\run-quality.py     # GX (needs MinIO on localhost:9000)
.\scripts\bench.ps1                                   # Iceberg demos + timings
.\.venv\Scripts\python.exe scripts\export-lineage.py  # static provenance
```

`verify.ps1` re-runs every `sql/*.sql` into a temp dir and compares with
`experiments/` (rowcount, monthly counts, snapshot totals, deterministic
queries). Run it after a rebuild + reload; exit code 1 means a mismatch.

## 4. Stop / full reset

```powershell
.\scripts\down.ps1              # terraform destroy (cluster + volumes deleted)
```

Data is re-downloadable (`download-data.ps1`) and reloadable (`run-ingest.ps1`);
nothing irreplaceable lives in the cluster. `up.ps1` after `down.ps1` is the
supported rebuild path (verified in Phase 10).

## 5. Troubleshoot (all observed on this machine)

| Symptom | Cause / fix |
|---|---|
| `docker info` fails | Start Docker Desktop, wait ~60 s |
| `terraform apply` hangs on `kind_cluster` | First pull of the node image (~1 GB); wait, retry |
| `minio-make-buckets` CrashLoop, then OK | Job raced MinIO startup; backoff retries succeed; chart now waits |
| `pull access denied for minio/minio` | Upstream images discontinued; we use `pgsty/minio` (D09) |
| Lakekeeper tag `0.13.5` not found | Tag has a `v` prefix: `v0.13.5` |
| Spark executors `UnknownHostException: <driver>` | Client-mode driver needs `spark.driver.host=<pod IP>` (chart sets it) |
| Spark `Unable to create executor due to ./xxx.jar` | `--packages` jars aren't fetchable by K8s executors; jars are baked into `/opt/spark/jars` |
| Spark executors exit 134 / SIGSEGV in libjvm | Iceberg vectorized reader vs this JVM/VM; `spark.sql.iceberg.vectorization.enabled=false` (D14); Java 17 + ParallelGC |
| `ModuleNotFoundError: yaml` in spark-runner | `pyyaml` baked into the image (Dockerfile) |
| Spark `MERGE` into 20 M rows kills executors | By design now: file ledger + append (D13) |
| `kubectl logs job/...` times out | Failed Job pods get GC'd; re-run via `spark-debug` pod + `scripts/submit-*.sh` |
| Trino queries fail on S3 | `fs.s3.enabled=true` is required (default false); check NodePort 30080 → host 8080 |
| RBAC `Forbidden ... deletecollection/patch` | `spark` Role covers pods/services/configmaps/pvc + patch (chart) |
| `pytest` hangs on Windows | Spark-local tests skip on win32 by design (D12); run them in `apache/spark:3.5.9` container |
| `run-ingest.ps1 -Month x` fails on `param()` | Use positional arg: `run-ingest.ps1 2024-01` (PS 5.1 parsing quirk on some hosts) |
| `up.ps1 ... 2>&1 | Out-File` aborts at docker build | PS 5.1 turns native stderr into terminating errors under `Stop`; run plainly or use `Start-Transcript` for logging |
| `helm lint infra/helm/argocd` fails | Not a chart (upstream chart + values); CI renders it instead |
| Old `spark-debug` pod has stale image/scripts | Delete + recreate after `kind load`; `kubectl cp` fresh scripts |
| WSL2 eats host RAM | Check `~/.wslconfig` (20 GB); restart Docker Desktop to apply |

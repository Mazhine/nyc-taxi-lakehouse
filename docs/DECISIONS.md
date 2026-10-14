# DECISIONS

Log each decision: context, options, choice, hypothesis. Ambiguities are resolved
by picking the most reasonable option and writing it here.

## D00 — Project root
- Context: working directory is `Projet Data Renforcement` (empty, not a repo).
- Choice: treat it as the `lakehouse-platform/` root from the spec (no extra nesting).
- Hypothesis: simpler paths, spec tree maps 1:1.

## D01 — kind over k3d
- Context: need a local single-node K8s for Docker Desktop/WSL2.
- Options: kind (0.33.0) vs k3d (wraps k3s).
- Choice: **kind**. Reason: no extra binary beyond Docker, Terraform provider
  `tehcyx/kind` exists, huge community, matches "single node" need.
  k3d/k3s is lighter but adds another distribution to pin and learn.
- Sources: kind 0.33.0 via winget 2026-10-14; kubectl 1.34.1 client OK.
- Hypothesis: kind image default (K8s ~1.34) fits Docker Desktop 4.78.0.

## D02 — Lakekeeper over Polaris/Nessie
- Context: need an Iceberg REST catalog, local, light, maintained (checked 2026-10-14).
- Options:
  - Apache Polaris (ASF top-level since Feb 2026, v1.8.0 Sep 2026, 17 recent
    contributors, JVM/Quarkus, broad engine support, RBAC + credential vending).
  - Lakekeeper (Rust single static binary, Apache-2.0, v0.13.5 Sep 2026,
    ~10 recent contributors, OpenFGA auth, needs Postgres).
  - Nessie (git-like branches, active but only ~3 recent contributors;
    merge into Polaris announced 2024 never happened as of mid-2026).
- Choice: **Lakekeeper 0.13.5**.
  - Why: single static binary, no JVM, tiny memory footprint — decisive on a
    20 GB WSL2 single node that also runs Trino + Spark + MinIO.
    Read-write Iceberg REST (Unity OSS is read-only), good Trino/Spark docs.
  - Trade-off: smaller community than Polaris; if Lakekeeper proves flaky,
    fallback is self-hosted Polaris (documented, same REST API for engines).
- Sources: Dremio Sep 2026 catalog review; Lakekeeper 0.13.5 release Sep 2026;
  Polaris graduation Feb 2026; Trino charts 1.44.0/app 483 Oct 2026.
- Hypothesis: Postgres 16 backend + MinIO S3 works from Lakekeeper docs quickstart.

## D03 — Spark 3.5.9 + Iceberg 1.6.1
- Context: need Spark-on-K8s writing Iceberg, stable on Python 3.12.
- Choice: **Spark 3.5.9** (Jul 2026 maintenance) + **Iceberg spark-runtime 1.6.1**
  (Spark 3.5 bundle). Spark 4.x exists (4.2.0 Jul 2026) but Iceberg/Scala-2.13
  integration is less battle-tested for this setup.
- Hypothesis: `apache/spark:3.5.9` image + `--packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1` works offline after first pull.

## D04 — Trino chart 1.44.0 / app 483
- Context: query engine with Iceberg connector on K8s.
- Choice: official `trino/trino` chart **1.44.0**, one worker, explicit limits.
- Source: trinodb/charts + ArtifactHUB, Oct 2026.

## D05 — Great Expectations over Soda
- Context: data quality with local versioned reports.
- Choice: **Great Expectations 1.3.10** (local file-store backends, no cloud).
  Soda Core leans on Soda Cloud for full value.
- Hypothesis: GX Data Docs as static HTML in `experiments/` is enough.

## D06 — WSL2 capped at 20 GB
- Context: 32 GB host, Docker Desktop WSL2 backend.
- Choice: `~/.wslconfig` with `memory=20GB, processors=8, swap=4GB`.
- Reason: leave ~12 GB to Windows/IDE while giving K8s room.

## D07 — TLC scope: 2024-01..06 + 2019-01 + 2023-01
- Context: yellow-taxi parquet months are ~60-80 MB each; need volume + schema drift.
- Choice: 6 recent months for benchmarks + 2 old months for contract-drift demos.
  Zone lookup CSV as reference table. Nothing versioned in git (`data/` ignored).
- Source: TLC trip-record page + CDN `d37ci6vzurychx.cloudfront.net/trip-data/`.
- Hypothesis: old files show added/renamed columns and type changes (verified in Phase 1).

## D08 — No Medallion wording, no Kafka, no Grafana/Loki, no MLflow
- Context: other projects already cover these; avoid redundancy.
- Choice: layer names are `raw → validated → trusted` (not bronze/silver/gold);
  batch incremental jobs only; health probes + `kubectl logs` only.

## D09 — MinIO upstream mort, fork pgsty/minio
- Context: spec asks MinIO. Verified 2026-10-14: upstream archived Feb 2026
  ("source-only distribution"), `minio/minio` gone from Docker Hub (~Sep 2026,
  `pull access denied`), `quay.io/minio/minio` 401 for anonymous pulls.
- Options: (a) build from source (heavy, no CVE backports), (b) SeaweedFS/Garage
  (not MinIO), (c) community fork with same S3 API/CLI/env.
- Choice: **pgsty/minio:RELEASE.2026-08-04T00-00-00Z**
  (digest sha256:b6bfe723…, pull verified) — MinIO-compatible S3 API, same
  `MINIO_*` vars, `mc`/`mcli` CLI, console :9001. Single 20 Gi volume, buckets
  `lakehouse` + `quarantine` created by a Job (`mc mb --ignore-existing`).
- Hypothesis: S3A clients (Spark, Trino, PyIceberg) see no difference.

## D10 — GitOps honnête sans remote
- Context: Argo CD syncs from Git, but this repo has no remote yet (100 % local).
- Choice: Argo CD installed with `infra/argocd/*` Application manifests ready;
  `scripts/up.ps1` applies the SAME charts via Helm in the meantime.
  No manual `kubectl` hidden: everything is in the repo. Once a remote exists,
  `kubectl apply -f infra/argocd/root-app.yaml` enables full GitOps sync.
- Hypothesis: acceptable per rule 6 (no hidden manual config; limitation dite).

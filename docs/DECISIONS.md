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

## D11 — Table pre-ingestion recréée (schéma corrigé)
- Context: Phase 3 smoke table had `source_file long` (wrong type for labels).
- Choice: dropped the EMPTY table and recreated it with
  `source_file string, row_hash string`. No data lost. Schema-evolution demos
  (add/rename/partition) happen on loaded data in Phase 7 instead.

## D12 — Tests Spark dans un conteneur Linux, pas sur l'hôte Windows
- Context: Spark local hangs on the Windows host (non-ASCII OneDrive path,
  winutils/HADOOP_HOME friction, OneDrive file latency).
- Choice: `tests/test_ingest_spark.py` runs in `apache/spark:3.5.9` container
  (12/12 green). Host runs ruff + 9 pure-python tests. Documented as-is.

## D13 — Idempotence par registre de fichiers + append (pas de MERGE global)
- Context: MERGE on (source_file, row_hash) worked into an empty/small table
  (6 months loaded), but replaying into the 20 M-row table kills executors
  (exit 134, repeated) on this 2×3g single node — full-target shuffle too big.
- Choice: file-level ledger. Each load first reads
  `SELECT DISTINCT source_file FROM <table>`; if the file label is present the
  run is a no-op (`skipped_already_loaded`, no quarantine rewrite either).
  Otherwise rows append. Immutable taxi files make file-level the right grain;
  `build_merge_sql()` stays as a tested utility for future upsert tables.
- Hypothesis: DISTINCT scan of one narrow column stays cheap; verified by replay.

## D14 — Lecteur vectorisé Iceberg désactivé + Java 17 + ParallelGC
- Context: toute lecture de la table Iceberg via Spark tuait les exécuteurs
  (exit 134, SIGSEGV libjvm : `G1BarrierSet`, `ciType::make`, `SymbolTable`),
  alors que le parquet brut via S3A passait (2 M lignes OK). Même un COUNT sur
  3 fichiers échouait (VerifyError).
- Options testées : ParallelGC seul (échec), TieredStopAtLevel=1 (échec),
  Java 17 Temurin (échec, autre frame), lecture S3A directe (OK).
- Choice: `spark.sql.iceberg.vectorization.enabled=false` (lecture row-based),
  Java 17 + ParallelGC conservés par prudence, exécuteurs 2×3 Go. DISTINCT sur
  20 M lignes OK, COUNT total OK, rejeu OK.
- Coût : lectures Spark plus lentes (mesuré en phase 7, pas estimé).
- Hypothesis: l'Arrow off-heap du lecteur vectorisé est incompatible avec
  cette JVM sous WSL2/Docker ; à re-tester sur une autre machine.

## D15 — Trino via chart officiel + catalogue lakehouse
- Context: requêtes SQL sur Iceberg via REST.
- Choice: chart officiel `trino/trino` **1.44.0** (app **483**) en wrapper local
  (`infra/helm/trino`, Chart.lock versionné, tgz ignoré) : 1 coordinateur
  (heap 2G, limites 2cpu/3Gi) + 1 worker (heap 3G, 2cpu/4Gi), NodePort 30080,
  catalogue `lakehouse` (REST `...:8181/catalog`, warehouse `warehouse`,
  `fs.s3.enabled=true`, endpoint MinIO in-cluster). Props conformes aux docs
  Trino 483 (REST catalog + native S3 FS).
- Résultat: 20 015 099 lignes lues, jointure zones OK. La JVM Trino (image
  officielle) lit Iceberg sans crash — le SIGSEGV est spécifique à Spark.

## D16 — Qualité GX 1.24 sur échantillons (pandas), pas sur le cluster
- Context: GX sur Spark/K8s ou Trino-SQLAlchemy = lourd et fragile ; les reads
  Iceberg host sont impossibles (DNS cluster).
- Choice: **great-expectations==1.24.0** (vérifié à la doc du jour), suite
  `yellow_trips` (7 expectations = règles du contrat), validée sur
  (a) 200 k lignes d'un fichier Iceberg de confiance téléchargé de MinIO
  → succès 100 %, (b) 20 k lignes de quarantaine → échec attendu
  (contrôle négatif : `fare_amount`, `total_amount` en cause).
- Rapports versionnés : `experiments/phase6_quality.json` + JSON GX ;
  Data Docs HTML construits en local uniquement (git-ignorés).

## D17 — Rétention d'expire à 1h (démo) + benchmarks via Trino
- Context: `expire_snapshots` exige retention >= min-retention (défaut 7j) ;
  tous les benchmarks doivent tourner sur la même machine, mêmes données.
- Choice: `iceberg.expire-snapshots.min-retention=1h` (et remove-orphan 1h)
  dans le catalogue Trino — réglage assumé de plateforme démo, pas de prod.
  Tous les benchmarks via Trino (JVM stable) : compaction (27→2 fichiers),
  clone partitionné par mois (CTAS), CTAS vs INSERT, time travel + rollback.
- Mesures: médiane sur 5 répétitions + stdev, fichiers/octets via `$files`,
  résultats bruts dans `experiments/phase7_*.json`. Rien d'estimé.

## D18 — Marquez écarté (ressources), provenance statique à la place
- Context: spec = Marquez SEULEMENT si les ressources le permettent.
  Mesuré le 14/10 : nœud unique, CPU limits 107 % (overcommit), mémoire limits
  67 % (~12,2 Gio). Tournent déjà : Argo CD (7 pods), MinIO, Postgres,
  Lakekeeper, Trino (2 pods ≈ 7 Gio de limites), pods Spark en rafales.
  Marquez = API + Web + Postgres + listener OpenLineage à re-valider, et une
  JVM de plus (même famille que le SIGSEGV Spark).
- État vérifié le 14/10 : upstream `MarquezProject/marquez` 0.50.0 (Java) ;
  fork `ilum/marquez` 0.54.0 (backend Rust, OpenLineage 2.0.2, moindre
  empreinte) + chart Helm avec Postgres optionnel.
- Choice: **pas de Marquez** — « un petit ensemble qui fonctionne vaut mieux
  qu'un grand ensemble qui plante ». Substituts réels : registre `source_file`
  (idempotence), snapshots Iceberg avec app-ids (phase5), motifs de
  quarantaine, + export statique `experiments/phase8_lineage.json` généré
  depuis ces artefacts mesurés (14 nœuds, 29 arêtes, rien d'inventé).
- Pour l'ajouter un jour : chart `ilum/marquez` 0.54.0 + `postgresql.enabled`,
  listener OpenLineage dans l'image spark-runner, +4 Gio de limites min.

## D19 - Vérification d'acceptation automatique + nettoyage de dette
- Context: la phase 10 validait le rebuild à la main (`git diff` des JSON) ;
  le dépôt gardait des restes obsolètes : `requirements.txt` vide, `bench.ps1`
  en stub, `.env` jamais lu, README avec `-Month` (syntaxe qui échoue).
- Choice: `scripts/verify.ps1` relance `sql/*.sql` dans un dossier temporaire
  et compare avec `experiments/` via `scripts/verify-results.py` (rowcount,
  comptes mensuels, total du dernier snapshot, requêtes déterministes 01/02/03/05).
  Code retour 1 au moindre écart. Les 3 tests Spark tournent en CI via
  `scripts/ci-spark-tests.sh` (image `apache/spark:3.5.9`). `.env.example`
  supprimé (credentials démo fixes dans les charts) ; `requirements.txt` pinné
  sur l'environnement vérifié ; `bench.ps1` délègue à `bench-iceberg.py`.
- Hypothesis: 01/02/03/05 sont déterministes ; 04 est comparée structurellement
  car les ids/timestamps de snapshots changent à chaque rebuild.
- Validé le 2026-10-19 sur un rebuild complet : 8/8 PASS, 20 015 099 lignes
  (`experiments/phase10_verify.txt`).

## D20 - Chargement des zones comme Job de première classe
- Context: en phase 10, `nyc.taxi_zones` était chargée à la main dans un pod de
  debug (`submit-probe.sh`). Un rebuild propre passait donc `verify.ps1` seulement
  si l'opérateur se souvenait de cette étape manuelle, et `sql/05_zone_names.sql`
  échouait sinon.
- Choice: `infra/helm/spark-jobs/templates/job-zones.yaml` + `scripts/load-zones.ps1`
  (même image, même RBAC, `helm template | kubectl apply`). Le script est
  idempotent : `load_zones.py` sort 0 si la table existe déjà.
- Consequence: le runbook est entièrement scripté (`up` → `upload-raw` →
  6 × `run-ingest` → `load-zones` → `verify`) et la jointure des 265 zones est
  reproductible sans intervention manuelle.


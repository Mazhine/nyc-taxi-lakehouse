# LEARNING_NOTES (français, 10–15 lignes max par phase)

Les résumés de phase sont ajoutés à la suite, au fil de l'eau.

## Phase 0 — Vérification environnement
- **Rôle** : prouver que la machine peut porter le projet avant d'écrire la moindre infra.
- **Pourquoi ce choix** : Docker Desktop + WSL2 + kind = un K8s local sans cloud ; versions épinglées et vérifiées aux sources officielles le 14/10/2026.
- **Comment ça marche** : on interroge chaque outil (`docker info`, `kubectl`, `helm`, `terraform`, `kind`), on démarre Docker Desktop, on installe helm 4.3.0 / terraform 1.16.5 / kind 0.33.0 via winget, on cappe WSL2 à 20 Go via `.wslconfig`.
- **Comment ça s'assemble** : ces versions alimentent tout le reste (chart Trino 1.44.0, Argo CD 3.5.5, Lakekeeper 0.13.5) ; preuves dans `experiments/phase0_env.txt`.
- **À retenir** : (1) Docker Desktop était installé mais éteint — `hello-world` valide le daemon ; (2) WSL2 sans limite mange la RAM Windows — `.wslconfig` obligatoire ; (3) winget installe mais le PATH du shell courant doit être rechargé.

## Phase 1 — Dépôt, outillage, données TLC
- **Rôle** : un dépôt Git qui se teste sans cluster + des données publiques réelles versionnées nulle part.
- **Pourquoi ce choix** : TLC yellow-taxi = gros volumes gratuits sans compte, Parquet mensuels ; 6 mois 2024 pour les benchmarks + 2019/2023 pour la dérive de schéma ; pas de Kafka ni de wording Medallion (autres projets).
- **Comment ça marche** : `scripts/download-data.ps1` télécharge 8 Parquets + zones ; `scripts/inspect-tlc.py` écrit `experiments/tlc_schema_report.json` ; contrat YAML + quarantaine testés par pytest ; Terraform `validate/fmt` verts.
- **Comment ça s'assemble** : `data/` (ignoré par git) nourrit l'ingestion Spark ; le contrat `yellow_trips.v1.yaml` pilote validation et quarantaine des phases 4/6.
- **À retenir** : (1) dérive réelle mesurée : `airport_fee` → `Airport_fee`, VendorID int64→int32, passenger_count double→int64, 31 M lignes / 500 Mo ; (2) YAML flow + crochets = quoter les types ; (3) 9 tests verts (contrats, quarantaine, idempotence).

## Phase 2 — Cluster Kubernetes + Argo CD
- **Rôle** : une fondation K8s reproductible en une commande, avec déploiement GitOps.
- **Pourquoi ce choix** : kind plutôt que k3d = juste Docker, provider Terraform `tehcyx/kind` 0.9.0 ; Argo CD pour sync auto depuis Git, santé visible.
- **Comment ça marche** : `terraform apply` crée le cluster kind (1 nœud, ports 9000/9001/8080/8181 mappés) ; `helm install` pose Argo CD 3.5.5 avec réplicas à 1 et limites mémoire explicites.
- **Comment ça s'assemble** : tout ce qui suit (MinIO, Lakekeeper, Trino) est déployé sur ce cluster ; `scripts/up.ps1` rejoue l'ensemble ; preuves dans `experiments/phase2_cluster.txt`.
- **À retenir** : (1) kind télécharge l'image nœud (~1 Go) — 1m14 ici ; (2) pas de metrics-server par défaut, `kubectl top` indisponible ; (3) le job d'init Redis reste `Completed`, c'est normal.

## Phase 3 — MinIO, catalogue Iceberg, tables
- **Rôle** : le socle de données — stockage objet, catalogue qui sait où sont les tables, première table.
- **Pourquoi ce choix** : MinIO amont étant mort (archivé fév. 2026, images supprimées), fork `pgsty/minio` compatible S3 ; Lakekeeper car binaire unique léger avec Postgres 16 ; charts Helm locaux avec limites explicites.
- **Comment ça marche** : 3 charts (minio, postgres, lakekeeper) ; Jobs de migration, bootstrap et création du warehouse `warehouse` ; PyIceberg crée le namespace `nyc` et la table `yellow_trips` dont le metadata.json atterrit dans MinIO.
- **Comment ça s'assemble** : Spark (phase 4) écrit via l'URI REST `...:8181/catalog` + token `dummy` ; Trino (phase 5) lit le même warehouse ; quarantaine = bucket dédié.
- **À retenir** : (1) tag Lakekeeper = `v0.13.5` avec `v`, pas `0.13.5` ; (2) Jobs K8s avec retry = idempotence d'infra ; (3) preuves dans `experiments/phase3_catalog.json`.

## Phase 4 — Ingestion Spark incrémentale, contrats, quarantaine
- **Rôle** : remplir la table Iceberg mois par mois sans doublons, en écartant les lignes invalides avec un motif.
- **Pourquoi ce choix** : spark-submit client-mode sur K8s (driver dans le pod Job, 2 exécuteurs) ; idempotence par registre `source_file` + append (le MERGE global OOM sur 20 M lignes) ; contrats YAML + quarantaine bucket dédié.
- **Comment ça marche** : image `spark-runner` (Spark 3.5.9 + jars Iceberg/S3A sur le classpath, Java 17) ; chaque Job lit `s3a://lakehouse/raw/`, normalise (casse/types), split valide/quarantaine, skip si déjà chargé. 6 mois 2024 ingérés.
- **Comment ça s'assemble** : écrit dans le warehouse Lakekeeper créé en phase 3 ; Trino (phase 5) lira la même table ; quarantaine relue en phase 6.
- **À retenir** : (1) 20 015 099 lignes valides + 317 994 en quarantaine (~1,6 %), rejeu 2024-01 = `skipped_already_loaded`, 0 fichier ajouté ; (2) jars `--packages` invisibles aux exécuteurs K8s → les baker dans l'image ; (3) lecteur vectorisé Iceberg = SIGSEGV JVM ici → désactivé et documenté (D14).

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

## Phase 5 — Trino et requêtes de démonstration
- **Rôle** : interroger la table Iceberg en SQL sans toucher à Spark.
- **Pourquoi ce choix** : chart officiel `trino/trino` 1.44.0/app 483 (pas de chart maison), 1 seul worker, catalogue Iceberg REST vers Lakekeeper + S3 natif vers MinIO.
- **Comment ça marche** : `helm install` (coordinateur + worker), `scripts/trino-query.py` joue `sql/*.sql` via le client Python sur `localhost:8080` et sauve les JSON dans `experiments/phase5_*.json`.
- **Comment ça s'assemble** : lit le même warehouse que Spark écrit ; la table `nyc.taxi_zones` (265 lignes, chargée par Spark) permet la jointure ; `$snapshots` nourrit la phase 7 (time travel).
- **À retenir** : (1) 20 015 099 lignes confirmées par deux moteurs ; (2) `fs.s3.enabled=true` est obligatoire (défaut false) ; (3) Trino lit Iceberg sans crash là où Spark-Temurin segfault — preuve par l'exécution.

## Phase 6 — Qualité des données
- **Rôle** : prouver par un tiers (GX) que la table de confiance est saine et que la quarantaine contient bien les lignes invalides.
- **Pourquoi ce choix** : Great Expectations 1.24 en local sur échantillons pandas — pas de cluster, pas de SQLAlchemy exotique ; contrôle négatif sur la quarantaine au lieu d'un simple « tout passe ».
- **Comment ça marche** : `scripts/run-quality.py` télécharge un fichier Iceberg + un fichier de quarantaine depuis MinIO, joue 7 expectations (les règles du contrat), écrit les JSON dans `experiments/`, construit les Data Docs en local.
- **Comment ça s'assemble** : la suite reflète `contracts/yellow_trips.v1.yaml` ; les violations détectées correspondent aux motifs `_quarantine_reason` de la phase 4.
- **À retenir** : (1) 200 k lignes trusted = 100 %, 20 k quarantaine = échec attendu ; (2) API GX 1.x : `BatchParameters` est un TypedDict, `to_json_dict()` pour sérialiser ; (3) versionner les JSON, pas le HTML.

## Phase 7 — Fonctionnalités Iceberg et benchmarks
- **Rôle** : démontrer que le format tient ses promesses (évolution, time travel, compaction) avec des chiffres mesurés, pas des slogans.
- **Pourquoi ce choix** : tout via Trino (stable ici) : `ADD/RENAME COLUMN` sans réécriture, `FOR VERSION AS OF` + `rollback_to_snapshot`, `EXECUTE optimize/expire_snapshots`, CTAS partitionné par mois ; 5 répétitions, médiane + stdev.
- **Comment ça marche** : `scripts/bench-iceberg.py` enchaîne les étapes et sauve `experiments/phase7_*.json` ; `$files`/`$snapshots` donnent fichiers et octets ; rowcount final = 20 015 099 (données intactes).
- **Comment ça s'assemble** : travaille sur la table des phases 4-5 ; expire réglé à 1h (D17) pour purger les 7 snapshots de démo ; les chiffres alimentent le tableau README.
- **À retenir** : (1) compaction 27→2 fichiers, requête 4,97s→3,49s (médianes) ; (2) partitionnement mois : 3,31s→2,38s ; CTAS 20 M lignes = 106s ; (3) time travel + rollback aller-retour vérifiés par comptages.

## Phase 8 — Lineage : écarté, documenté
- **Rôle** : tracer d'où viennent les données — sans casser ce qui marche.
- **Pourquoi ce choix** : nœud à 67 % mémoire / 107 % CPU en limites avec Trino+Spark ; Marquez (même Rust 0.54.0) = 3 charges + re-validation du runner ; la spec autorise l'écart documenté.
- **Comment ça marche** : `scripts/export-lineage.py` assemble `experiments/phase8_lineage.json` (14 nœuds, 29 arêtes) depuis snapshots, résumés d'ingestion, contrats et quarantaine — que du mesuré.
- **Comment ça s'assemble** : s'appuie sur le registre `source_file`, les app-ids des snapshots et les motifs de quarantaine des phases précédentes.
- **À retenir** : (1) petit ensemble qui marche > grand qui plante ; (2) la provenance peut être statique et honnête ; (3) Marquez 0.54.0-Rust = la cible si un jour +4 Gio.

## Phase 9 — CI, documentation, runbook
- **Rôle** : figer la qualité (tests auto) et rendre le projet réutilisable sans son auteur.
- **Pourquoi ce choix** : GitHub Actions sans cluster (lint, unit, validate, helm lint, render + kubeconform v0.8.0) ; README avec mesures uniquement mesurées ; runbook avec chaque panne réellement vue.
- **Comment ça marche** : `scripts/test.ps1` = miroir local de la CI ; `helm template` + kubeconform valident les 5 charts ; `argocd` (pas un chart) est vérifié par rendu upstream.
- **Comment ça s'assemble** : la CI protège tout le code des phases 0-8 ; la phase 10 rejouera `up.ps1`/`down.ps1` pour valider le runbook.
- **À retenir** : (1) chart argocd = values seules → pas de `helm lint` ; (2) kubeconform `-ignore-missing-schemas` pour les CR ; (3) `ruff format --check` en CI oblige à formater avant de committer.

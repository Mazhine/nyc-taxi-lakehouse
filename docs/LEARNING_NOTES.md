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

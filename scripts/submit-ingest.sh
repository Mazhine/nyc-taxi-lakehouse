#!/bin/bash
# Debug helper mirroring infra/helm/spark-jobs/templates/job-ingest.yaml.
# Runs inside a spark-runner pod (kubectl exec). Args: MONTH [LIMIT].
# The Helm Job is the source of truth; this script exists for quick iteration.
set -eux
MONTH="${1:-2024-01}"
LIMIT_ARGS=""
# Optional second argument caps the input rows (fast smoke runs).
if [ -n "${2:-}" ]; then LIMIT_ARGS="--limit $2"; fi
# Client-mode drivers are not reachable by DNS, so advertise the pod IP.
DRIVER_IP="$(hostname -i | awk '{print $1}')"
/opt/spark/bin/spark-submit \
  --master k8s://https://kubernetes.default.svc \
  --deploy-mode client \
  --name "ingest-${MONTH}" \
  --conf spark.kubernetes.namespace=lakehouse \
  --conf spark.kubernetes.container.image=lakehouse/spark-runner:3.5.9-0.1.0 \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
  --conf spark.driver.host="$DRIVER_IP" \
  --conf spark.driver.bindAddress=0.0.0.0 \
  --conf spark.driver.port=22222 \
  --conf spark.driver.blockManager.port=22223 \
  --conf spark.driver.memory=1g \
  --conf "spark.driver.extraJavaOptions=-XX:+UseParallelGC" \
  --conf "spark.executor.extraJavaOptions=-XX:+UseParallelGC" \
  --conf spark.executor.instances=2 \
  --conf spark.executor.memory=3g \
  --conf spark.executor.cores=1 \
  --conf spark.executorEnv.PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  --conf spark.executorEnv.PYSPARK_PYTHON=python3 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.iceberg.vectorization.enabled=false \
  local:///opt/spark/jobs/src/ingestion/ingest.py \
  --input "s3a://lakehouse/raw/yellow_tripdata_${MONTH}.parquet" \
  --table lakekeeper.nyc.yellow_trips \
  --contract /opt/spark/jobs/contracts/yellow_trips.v1.yaml \
  --source-file "yellow_tripdata_${MONTH}" \
  --quarantine-path s3a://quarantine/yellow_trips \
  --catalog-uri http://lakekeeper.lakehouse.svc.cluster.local:8181/catalog \
  --warehouse warehouse \
  --s3-endpoint http://minio.lakehouse.svc.cluster.local:9000 \
  --master k8s://https://kubernetes.default.svc \
  $LIMIT_ARGS

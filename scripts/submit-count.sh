#!/bin/bash
# Count helper mirroring submit-ingest.sh conf (k8s client mode, 1 small executor).
# Kept as a debugging aid; prefer the maintenance job for scheduled runs.
set -eu
DRIVER_IP="$(hostname -i | awk '{print $1}')"
/opt/spark/bin/spark-submit \
  --master k8s://https://kubernetes.default.svc \
  --deploy-mode client \
  --name table-count \
  --conf spark.kubernetes.namespace=lakehouse \
  --conf spark.kubernetes.container.image=lakehouse/spark-runner:3.5.9-0.1.0 \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
  --conf spark.driver.host="$DRIVER_IP" \
  --conf spark.driver.bindAddress=0.0.0.0 \
  --conf spark.driver.port=22222 \
  --conf spark.driver.blockManager.port=22223 \
  --conf spark.driver.memory=1g \
  --conf spark.executor.instances=1 \
  --conf spark.executor.memory=1g \
  --conf spark.executor.cores=1 \
  --conf spark.executorEnv.PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  --conf spark.executorEnv.PYSPARK_PYTHON=python3 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  local:///opt/spark/jobs/src/maintenance/table_count.py \
  --table lakekeeper.nyc.yellow_trips \
  --catalog-uri http://lakekeeper.lakehouse.svc.cluster.local:8181/catalog \
  --s3-endpoint http://minio.lakehouse.svc.cluster.local:9000 \
  --master k8s://https://kubernetes.default.svc

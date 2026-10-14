#!/bin/bash
# One-off probe submitter (debugging aid). Args: APP_PY [EXTRA_CONFS...]
# Not used by automation; infra/helm/spark-jobs is the source of truth.
set -eu
APP_PY="${1:-/tmp/distinct.py}"
DRIVER_IP="$(hostname -i | awk '{print $1}')"
/opt/spark/bin/spark-submit \
  --master k8s://https://kubernetes.default.svc \
  --deploy-mode client \
  --name probe \
  --conf spark.kubernetes.namespace=lakehouse \
  --conf spark.kubernetes.container.image=lakehouse/spark-runner:3.5.9-0.1.0 \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
  --conf spark.driver.host="$DRIVER_IP" \
  --conf spark.driver.bindAddress=0.0.0.0 \
  --conf spark.driver.port=22222 \
  --conf spark.driver.blockManager.port=22223 \
  --conf spark.driver.memory=1g \
  --conf "spark.driver.extraJavaOptions=-XX:+UseParallelGC -XX:TieredStopAtLevel=1" \
  --conf "spark.executor.extraJavaOptions=-XX:+UseParallelGC -XX:TieredStopAtLevel=1" \
  --conf spark.executor.instances=1 \
  --conf spark.executor.memory=3g \
  --conf spark.executor.cores=1 \
  --conf spark.kubernetes.executor.deleteOnTermination=false \
  --conf spark.executorEnv.PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  --conf spark.executorEnv.PYSPARK_PYTHON=python3 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.iceberg.vectorization.enabled=false \
  "file://${APP_PY}"

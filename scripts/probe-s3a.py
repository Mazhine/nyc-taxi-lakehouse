"""Probe: read one Iceberg data file via plain S3A (bypass Iceberg reader)."""

from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.master("k8s://https://kubernetes.default.svc")
    .appName("s3a-probe")
    .config("spark.kubernetes.namespace", "lakehouse")
    .config("spark.kubernetes.container.image", "lakehouse/spark-runner:3.5.9-0.1.0")
    .config("spark.kubernetes.authenticate.driver.serviceAccountName", "spark")
    .config("spark.kubernetes.executor.deleteOnTermination", "false")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio.lakehouse.svc.cluster.local:9000")
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin-local-demo-only")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .getOrCreate()
)
path = (
    "s3a://lakehouse/iceberg/01a13a70-13b8-7c51-bb10-2fe69a49779e/data/"
    "00000-13-57ae5071-fd7e-40bf-8b3e-0bf0ac0742de-0-00001.parquet"
)
n = spark.read.parquet(path).count()
print("RESULT-S3A-COUNT=" + str(n))
spark.stop()

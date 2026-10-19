"""Probe: ``SELECT DISTINCT source_file`` over the table (JVM-stability check).

Debug-only script run **inside** the cluster (submitted by
``scripts/submit-probe.sh``). It was used to diagnose driver/executor JVM
crashes on the 20M-row table. It prints a single ``RESULT-DISTINCT=`` line so the
answer is easy to grep from the pod log.
"""

from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.master("k8s://https://kubernetes.default.svc")
    .appName("distinct-probe")
    .config("spark.kubernetes.namespace", "lakehouse")
    .config("spark.kubernetes.container.image", "lakehouse/spark-runner:3.5.9-0.1.0")
    .config("spark.kubernetes.authenticate.driver.serviceAccountName", "spark")
    .config("spark.kubernetes.executor.deleteOnTermination", "false")
    .config(
        "spark.sql.extensions",
        "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    )
    .config("spark.sql.catalog.lakekeeper", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.lakekeeper.type", "rest")
    .config(
        "spark.sql.catalog.lakekeeper.uri",
        "http://lakekeeper.lakehouse.svc.cluster.local:8181/catalog",
    )
    .config("spark.sql.catalog.lakekeeper.warehouse", "warehouse")
    .config("spark.sql.catalog.lakekeeper.token", "dummy")
    .config("spark.sql.catalog.lakekeeper.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    .config(
        "spark.sql.catalog.lakekeeper.s3.endpoint", "http://minio.lakehouse.svc.cluster.local:9000"
    )
    .config("spark.sql.catalog.lakekeeper.s3.path-style-access", "true")
    .config("spark.sql.catalog.lakekeeper.s3.access-key-id", "minioadmin")
    .config("spark.sql.catalog.lakekeeper.s3.secret-access-key", "minioadmin-local-demo-only")
    # Iceberg vectorized reads SIGSEGV on this JVM/JDK combination (D14).
    .config("spark.sql.iceberg.vectorization.enabled", "false")
    .getOrCreate()
)
print(
    "RESULT-DISTINCT="
    + str(
        sorted(
            [
                r["source_file"]
                for r in spark.sql(
                    "SELECT DISTINCT source_file FROM lakekeeper.nyc.yellow_trips"
                ).collect()
            ]
        )
    )
)
spark.stop()

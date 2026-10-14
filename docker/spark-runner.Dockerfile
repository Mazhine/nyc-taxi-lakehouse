FROM apache/spark:3.5.9
# Spark runner for lakehouse ingestion jobs (spark-submit --master k8s client mode).
# Pinned base digest (pulled 2026-10-14): sha256:af02a459c8706e031c835c16f9db3c463816776e2543dd0f828af65606bcf392
USER 0
# Java 17 (Temurin JRE): the base image's Temurin 11.0.31 crashes with SIGSEGV
# in libjvm (ciType::make, G1 barrier) on heavy Spark tasks in this VM.
# Spark 3.5 supports Java 17. Pinned asset, verified at build time.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fSL -o /tmp/jre17.tgz \
      https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jre_x64_linux_hotspot_17.0.20.1_1.tar.gz \
 && mkdir -p /opt/java17 && tar -xzf /tmp/jre17.tgz -C /opt/java17 --strip-components=1 \
 && rm /tmp/jre17.tgz && /opt/java17/bin/java -version
ENV JAVA_HOME=/opt/java17
# Pure-python deps of src/ (contract YAML parsing in the driver).
RUN python3 -m pip install --no-cache-dir pyyaml
# Pre-resolve Iceberg/S3A jars into /root/.ivy2 so every Job pod does NOT
# re-download ~350 MB from Maven Central at startup.
ENV LAKEHOUSE_PACKAGES="org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262"
RUN /opt/spark/bin/spark-submit --packages "$LAKEHOUSE_PACKAGES" --master local \
      --class org.apache.spark.examples.SparkPi \
      local:///opt/spark/examples/jars/spark-examples_2.12-3.5.9.jar 1
# Rename Ivy-cached jars to Maven names AND put them on the default classpath
# ($SPARK_HOME/jars): --packages/--jars ship driver-local relative paths that
# k8s executors cannot fetch, so the jars must already be inside the image.
RUN mkdir -p /opt/spark/extra-jars && \
    cp /root/.ivy2/jars/org.apache.iceberg_iceberg-spark-runtime-3.5_2.12-1.6.1.jar \
       /opt/spark/extra-jars/iceberg-spark-runtime-3.5_2.12-1.6.1.jar && \
    cp /root/.ivy2/jars/org.apache.iceberg_iceberg-aws-bundle-1.6.1.jar \
       /opt/spark/extra-jars/iceberg-aws-bundle-1.6.1.jar && \
    cp /root/.ivy2/jars/org.apache.hadoop_hadoop-aws-3.3.4.jar \
       /opt/spark/extra-jars/hadoop-aws-3.3.4.jar && \
    cp /root/.ivy2/jars/com.amazonaws_aws-java-sdk-bundle-1.12.262.jar \
       /opt/spark/extra-jars/aws-java-sdk-bundle-1.12.262.jar && \
    cp /root/.ivy2/jars/org.wildfly.openssl_wildfly-openssl-1.0.7.Final.jar \
       /opt/spark/extra-jars/wildfly-openssl-1.0.7.Final.jar && \
    cp /opt/spark/extra-jars/*.jar /opt/spark/jars/ && \
    ls /opt/spark/jars | grep -E "iceberg|hadoop-aws|aws-java|wildfly"
ENV LAKEHOUSE_JARS="file:///opt/spark/extra-jars/iceberg-spark-runtime-3.5_2.12-1.6.1.jar,file:///opt/spark/extra-jars/iceberg-aws-bundle-1.6.1.jar,file:///opt/spark/extra-jars/hadoop-aws-3.3.4.jar,file:///opt/spark/extra-jars/aws-java-sdk-bundle-1.12.262.jar,file:///opt/spark/extra-jars/wildfly-openssl-1.0.7.Final.jar"
COPY src /opt/spark/jobs/src
COPY contracts /opt/spark/jobs/contracts
ENV PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip
ENV SPARK_JOBS_HOME=/opt/spark/jobs
WORKDIR /opt/spark/jobs

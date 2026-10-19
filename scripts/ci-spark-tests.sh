#!/usr/bin/env bash
# Run the Spark transform tests inside apache/spark:3.5.9 (used by CI and locally).
#
# The host Windows environment cannot run these tests (PySpark has no win32
# worker here), so they are containerized. The official Spark image already
# ships Python + py4j; we only add pytest/pyyaml and point PYTHONPATH at the
# repo (mounted at /work) plus Spark's own Python libraries.
set -euo pipefail
export PYTHONPATH="/work:${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip:${PYTHONPATH:-}"
python3 -m pip install --quiet --disable-pip-version-check \
  --retries 5 --timeout 60 pytest==9.1.1 pyyaml==6.0.3
python3 -m pytest -q tests/test_ingest_spark.py

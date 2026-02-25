ARG MLFLOW_VERSION=v3.10.0
FROM ghcr.io/mlflow/mlflow:${MLFLOW_VERSION}

# Bake in PostgreSQL + S3 drivers so we never pip-install at runtime
RUN pip install --no-cache-dir psycopg2-binary boto3

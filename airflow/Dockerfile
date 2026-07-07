FROM apache/airflow:2.9.2

USER root
RUN apt-get update && apt-get install -y git && apt-get clean

# Install dbt-snowflake
RUN pip install --no-cache-dir dbt-snowflake==1.9.0

USER airflow

# Copy project code into image
COPY --chown=airflow:root ingestion/ /opt/airflow/govcontract/ingestion/
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/
COPY --chown=airflow:root airflow/scripts/ /opt/airflow/govcontract/airflow/scripts/

# Install ingestion dependencies
RUN pip install --no-cache-dir \
    snowflake-connector-python==3.10.0 \
    cryptography \
    azure-identity==1.17.1 \
    azure-keyvault-secrets==4.8.0 \
    openai>=1.50.0 \
    requests==2.32.3 \
    python-dotenv==1.0.1

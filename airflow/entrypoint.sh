#!/bin/bash
set -e

# Initialize DB
airflow db migrate

# Create admin user - force password reset if user exists
airflow users create \
    --username admin \
    --password GovContract2026x \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email yezavit@yahoo.com || true

airflow users reset-password \
    --username admin \
    --password GovContract2026x

# Start scheduler in background
airflow scheduler &

# Start webserver in foreground
exec airflow webserver --port 8080

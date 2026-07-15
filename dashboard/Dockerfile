FROM python:3.11-slim

WORKDIR /app

COPY requirements-streamlit.txt .
RUN pip install --no-cache-dir -r requirements-streamlit.txt

COPY ingestion/snowflake_conn.py ingestion/
COPY ingestion/keyvault.py ingestion/
COPY ingestion/search_index.py ingestion/
COPY dashboard/app.py .

ENV PYTHONPATH=/app/ingestion

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]

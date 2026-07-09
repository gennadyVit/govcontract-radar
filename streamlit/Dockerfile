FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-streamlit.txt .
RUN pip install --no-cache-dir -r requirements-streamlit.txt

COPY streamlit/ ./streamlit/

EXPOSE 8000

CMD ["streamlit", "run", "streamlit/app.py", \
     "--server.port", "8000", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]

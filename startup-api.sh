#!/bin/bash
pip install --upgrade pip
pip install -r requirements-api.txt --no-deps
pip install -r requirements-api.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000

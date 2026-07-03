#!/bin/bash
pip install --upgrade pip
pip install -r requirements-streamlit.txt
streamlit run streamlit/app.py --server.port 8000 --server.address 0.0.0.0

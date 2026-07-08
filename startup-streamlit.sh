#!/bin/bash
ANTENV=$(echo $PYTHONPATH | tr ':' '\n' | grep antenv | head -1 | sed 's|/lib/python.*||')
export PATH="$ANTENV/bin:$PATH"
streamlit run streamlit/app.py --server.port 8000 --server.address 0.0.0.0 --server.headless true

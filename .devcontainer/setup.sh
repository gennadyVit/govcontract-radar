#!/bin/bash
set -e

pip install -r requirements.txt
curl -sSL install.astronomer.io | sudo bash -s

# load non-sensitive Snowflake config (DB/schema/warehouse) into every shell
echo "set -a; source \$(pwd)/.env.codespace; set +a" >> ~/.bashrc

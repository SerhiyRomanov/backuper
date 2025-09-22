#!/bin/bash
set -x
set -e

cp EXAMPLE-docker-compose.yml docker-compose.yml
cp src/EXAMPLE-config.yaml src/config.yaml

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "Done"

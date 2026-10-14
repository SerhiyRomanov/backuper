#!/usr/bin/env bash

set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

echo "[+] Installing dependencies"
apt-get install -y python3 python3-yaml borgbackup cron openssh-client
exec /usr/bin/python3 "$PROJECT_DIR/setup_job.py" "$@"

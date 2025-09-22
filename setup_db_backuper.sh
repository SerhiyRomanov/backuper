#!/bin/bash
set -e
set -x

# === CONFIG ===
PROJECT_DIR="$(pwd)"
CONFIG_FILE="config.yaml"

# === INSTALL DEPENDENCIES ===
echo "[+] Installing dependencies"
apt-get update && apt-get install -y cron pigz docker-cli

# === SETUP CRON ===
echo "[+] Setting up cron job"
CRON_SCHEDULE=$(grep cron_schedule "$CONFIG_FILE" | awk '{print $2}')

echo $CRON_SCHEDULE python3 PROJECT_DIR/db_backup.py PROJECT_DIR/config.yaml >> /var/log/backuper/db_backuper.log 2>&1\" > /etc/cron.d/db_backuper
chmod 0644 /etc/cron.d/db_backuper && crontab /etc/cron.d/db_backuper

crontab -l

echo "[✓] db_backuper installed and scheduled"

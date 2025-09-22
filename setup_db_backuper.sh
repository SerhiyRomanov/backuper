#!/bin/bash
set -xe

# === CONFIG ===
PROJECT_DIR="$(pwd)"
CONFIG_FILE="config.yaml"

# === INSTALL DEPENDENCIES ===
echo "[+] Installing dependencies"
apt-get update && apt-get install -y yq cron pigz docker-cli

# === SETUP CRON ===
echo "[+] Setting up cron job"
CRON_SCHEDULE=$(yq '.cron_schedule_db' $CONFIG_FILE)

echo $CRON_SCHEDULE python3 PROJECT_DIR/db_backup.py PROJECT_DIR/config.yaml >> /var/log/backuper/db_backuper.log 2>&1\" > /etc/cron.d/db_backuper
chmod 0644 /etc/cron.d/db_backuper && crontab /etc/cron.d/db_backuper

crontab -l

echo "[✓] db_backuper installed and scheduled"

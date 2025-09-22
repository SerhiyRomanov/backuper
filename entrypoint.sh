#!/bin/sh
set -e

CONFIG_FILE="/app/config.yaml"
CRON_SCHEDULE=$(yq '.cron_schedule' $CONFIG_FILE)

echo "$SCHEDULE root python3 /app/backup.py /app/config.yaml >> /var/log/backuper/cron_stdout.log 2>&1" > /etc/cron.d/pg_backuper
chmod 0644 /etc/cron.d/backupjob
crontab /etc/cron.d/backupjob

echo "[+] Starting cron with schedule: $CRON_SCHEDULE"
cron -f

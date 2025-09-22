#!/bin/sh
set -xe

CONFIG_FILE="/app/config.yaml"
CRON_SCHEDULE=$(yq '.cron_schedule_files' $CONFIG_FILE)
echo "cron schedule is $CRON_SCHEDULE"

echo "$CRON_SCHEDULE python3 /app/backup.py /app/config.yaml >> /var/log/backuper/cron_stdout.log 2>&1" > /etc/cron.d/backupjob
chmod 0644 /etc/cron.d/backupjob
crontab /etc/cron.d/backupjob

echo "[+] Starting cron with schedule: $CRON_SCHEDULE"
cron -f

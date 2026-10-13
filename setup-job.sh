#!/usr/bin/env bash

set -euo pipefail
trap 'echo "Error: setup failed at line $LINENO." >&2' ERR

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <config_file>" >&2
    exit 1
fi
if [[ $EUID -ne 0 ]]; then
    echo "Error: run this script as root (sudo bash $0 <config_file>)." >&2
    exit 1
fi
if [[ ! -f "$1" ]]; then
    echo "Error: configuration file not found: $1" >&2
    exit 1
fi

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG_FILE=$(realpath -- "$1")

echo "[+] Installing dependencies"
apt-get install -y borgbackup yq python3-yaml cron openssh-client
borg --version

read_config() {
    yq -er ".$1 | select(. != null and . != \"\")" "$CONFIG_FILE"
}

REPOSITORY_PATH=$(read_config repository_path)
REPOSITORY_PORT=$(read_config repository_port)
PRIVATE_KEY_PATH=$(read_config private_key_path)
CRON_FILENAME=$(read_config cron_filename)
CRON_SCHEDULE=$(read_config cron)
SSH_TARGET=${REPOSITORY_PATH#ssh://}

cd -- "$PROJECT_DIR"
if [[ "$PRIVATE_KEY_PATH" == "~/"* ]]; then
    PRIVATE_KEY_PATH="$HOME/${PRIVATE_KEY_PATH:2}"
fi
PRIVATE_KEY_PATH=$(realpath -- "$PRIVATE_KEY_PATH")
BACKUP_SCRIPT=$(realpath -- "$CRON_FILENAME")
if [[ ! -f "$PRIVATE_KEY_PATH" || ! -f "$BACKUP_SCRIPT" ]]; then
    echo "Error: the SSH private key and backup script must exist." >&2
    exit 1
fi

LOG_FILE="$PROJECT_DIR/logs/$(basename -- "$BACKUP_SCRIPT").log"
printf -v CRON_COMMAND 'cd %q && /usr/bin/python3 %q %q >> %q 2>&1' \
    "$PROJECT_DIR" "$BACKUP_SCRIPT" "$CONFIG_FILE" "$LOG_FILE"
# Cron interprets percent signs even inside shell quotes.
CRON_COMMAND=${CRON_COMMAND//%/\\%}
JOB_ID=$(printf '%s' "$CONFIG_FILE" | sha256sum)
CRON_FILE="/etc/cron.d/backuper-${JOB_ID:0:16}"

# Validate syntax without replacing or modifying any user's crontab.
printf '%s %s\n' "$CRON_SCHEDULE" "$CRON_COMMAND" | crontab -n -

if [[ "$(basename -- "$BACKUP_SCRIPT")" == "backup-pg-db.py" ]]; then
    apt-get install -y postgresql-client pigz
fi

echo "[+] Installing SSH public key"
ssh-copy-id -i "$PRIVATE_KEY_PATH" -p "$REPOSITORY_PORT" -s "$SSH_TARGET"

echo "[+] Initializing Borg repository"
/usr/bin/python3 "$PROJECT_DIR/borg_wrapper.py" -c "$CONFIG_FILE" init

# Publish the job only after SSH setup and repository initialization succeed.
echo "[+] Installing cron job: $CRON_FILE"
mkdir -p -- "$PROJECT_DIR/logs" /etc/cron.d
CRON_TEMP=$(mktemp /etc/cron.d/.backuper-XXXXXX)
trap 'rm -f -- "$CRON_TEMP"' EXIT
{
    printf '# Managed by backuper setup-job.sh\n'
    printf 'SHELL=/bin/bash\n'
    printf 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
    printf '%s root %s\n' "$CRON_SCHEDULE" "$CRON_COMMAND"
} > "$CRON_TEMP"
chown root:root "$CRON_TEMP"
chmod 0644 "$CRON_TEMP"
mv -f -- "$CRON_TEMP" "$CRON_FILE"
echo "Done. Backup scheduled in $CRON_FILE; user crontabs were not modified."

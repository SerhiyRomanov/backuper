#!/usr/bin/env bash

set -euo pipefail
trap 'echo "Error: setup failed at line $LINENO." >&2' ERR

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG_FILE=$(realpath -- "$1")

echo "[+] Installing dependencies"
apt-get install -y borgbackup yq python3-yaml cron openssh-client
borg --version

read_config() {
    yq -r ".general.$1" "$CONFIG_FILE"
}

REPOSITORY_PATH=$(read_config repository_path)
REPOSITORY_PORT=$(read_config repository_port)
PRIVATE_KEY_PATH=$(read_config private_key_path)
SSH_TARGET=${REPOSITORY_PATH#ssh://}

cd -- "$PROJECT_DIR"
if [[ "$PRIVATE_KEY_PATH" == "~/"* ]]; then
    PRIVATE_KEY_PATH="$HOME/${PRIVATE_KEY_PATH:2}"
fi
PRIVATE_KEY_PATH=$(realpath -- "$PRIVATE_KEY_PATH")
LOG_FILE="$PROJECT_DIR/logs/backuper.log"
printf -v CRON_COMMAND 'cd %q && /usr/bin/python3 %q -c %q >> %q 2>&1' \
    "$PROJECT_DIR" "$PROJECT_DIR/backuper.py" "$CONFIG_FILE" "$LOG_FILE"
# Cron interprets percent signs even inside shell quotes.
CRON_COMMAND=${CRON_COMMAND//%/\\%}
JOB_ID=$(printf '%s' "$CONFIG_FILE" | sha256sum)
CRON_FILE="/etc/cron.d/backuper-${JOB_ID:0:16}"

if [[ "$(yq -r 'any(.jobs[]; .source == "postgresql")' "$CONFIG_FILE")" == "true" ]]; then
    apt-get install -y postgresql-client pigz
fi

echo "[+] Installing SSH public key"
ssh-copy-id -i "$PRIVATE_KEY_PATH" -p "$REPOSITORY_PORT" -s "$SSH_TARGET"

echo "[+] Initializing Borg repository"
/usr/bin/python3 "$PROJECT_DIR/cli.py" -c "$CONFIG_FILE" init

# Publish the job only after SSH setup and repository initialization succeed.
echo "[+] Installing cron job: $CRON_FILE"
mkdir -p -- "$PROJECT_DIR/logs" /etc/cron.d
CRON_TEMP=$(mktemp /etc/cron.d/.backuper-XXXXXX)
trap 'rm -f -- "$CRON_TEMP"' EXIT
{
    printf '# Managed by backuper setup-job.sh\n'
    printf 'SHELL=/bin/bash\n'
    printf 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
    printf '* * * * * root %s\n' "$CRON_COMMAND"
} > "$CRON_TEMP"
chown root:root "$CRON_TEMP"
chmod 0644 "$CRON_TEMP"
mv -f -- "$CRON_TEMP" "$CRON_FILE"
echo "Done. Backup scheduled in $CRON_FILE; user crontabs were not modified."

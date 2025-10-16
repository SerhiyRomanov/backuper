#!/usr/bin/env bash

CONFIG_FILE=$1
if [ -z "$CONFIG_FILE" ]; then
    echo "Usage: $0 <config_file>"
    exit 1
fi

set -xe

apt install -y borgbackup yq
borg --version

export REPOSITORY_PATH=$(yq -r '.repository_path' "$CONFIG_FILE")
export REPOSITORY_PORT=$(yq -r '.repository_port' "$CONFIG_FILE")
export REPOSITORY_NAME=$(yq -r '.repository_name' "$CONFIG_FILE")
export PRIVATE_KEY_PATH=$(yq -r '.private_key_path' "$CONFIG_FILE")

export BORG_PASSPHRASE=$(yq -r '.repository_passphrase' "$CONFIG_FILE")
export BORG_RSH="ssh -v -o IdentitiesOnly=yes -i ${PRIVATE_KEY_PATH} "

# === SETUP CRON ===
echo "[+] Setting up cron job"
export CRON_FILENAME=$(yq -r '.cron_filename' "$CONFIG_FILE")
export CRON_SCHEDULE=$(yq -r '.cron' $CONFIG_FILE)

mkdir -p "$(pwd)/logs"

echo "${CRON_SCHEDULE} /bin/bash $(pwd)/${CRON_FILENAME} $(pwd)/${CONFIG_FILE} >> $(pwd)/logs/${CRON_FILENAME}.log 2>&1" > /etc/cron.d/${CRON_FILENAME}.conf

chmod 0644 /etc/cron.d/${CRON_FILENAME}.conf && crontab /etc/cron.d/${CRON_FILENAME}.conf
crontab -l

# === Copy keys ===
ssh-copy-id -i ${PRIVATE_KEY_PATH} -p $REPOSITORY_PORT -s $REPOSITORY_PATH

# === Setup repo ===
bash borg.sh $CONFIG_FILE "init --encryption=repokey --remote-path=borg-1.4 $REPOSITORY_PATH:$REPOSITORY_PORT/./$REPOSITORY_NAME"

echo "Done"

#!/usr/bin/env bash

CONFIG_FILE=$1
if [ -z "$CONFIG_FILE" ]; then
    echo "Usage: $0 <config_file>"
    exit 1
fi

set -xe

exec > >(tee -i ${LOG})
exec 2>&1

echo "###### Backup started: $(date) ######"

export REPOSITORY_PATH=$(yq -r '.repository_path' "$CONFIG_FILE")
export REPOSITORY_PORT=$(yq -r '.repository_port' "$CONFIG_FILE")
export REPOSITORY_NAME=$(yq -r '.repository_name' "$CONFIG_FILE")
export PRIVATE_KEY_PATH=$(yq -r '.private_key_path' "$CONFIG_FILE")
export BORG_PASSPHRASE=$(yq -r '.repository_passphrase' "$CONFIG_FILE")
export REPO=$REPOSITORY_PATH:$REPOSITORY_PORT/./$REPOSITORY_NAME

export BORG_RSH="ssh -vvv -o IdentitiesOnly=yes -i ${PRIVATE_KEY_PATH}"

export INCLUDE_FOLDERS=$(yq -r '.include_folders | join(" ")' "$CONFIG_FILE")
export EXCLUDE_FOLDERS=$(yq -r '.exclude_folders | map("--exclude " + .) | join(" ")' "$CONFIG_FILE")


echo "Transfer files ..."
borg create -v --stats -C zstd,3 \
    $REPO::'{now:%Y-%m-%d-%H-%M}'  \
    $INCLUDE_FOLDERS \
    $EXCLUDE_FOLDERS

borg prune -v --list --stats \
  $REPO \
  $(yq -r '.borg_prune_params | join(" ")' "$CONFIG_FILE")

borg compact --progress $REPO

echo "###### Backup ended: $(date) ######"

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
umask 077

for pair in \
  '.env.example:.env' \
  'docker-compose.example.yml:docker-compose.yml' \
  'borgmatic/config.yaml.example:borgmatic/config.yaml'; do
  source_file=${pair%%:*}
  target_file=${pair#*:}
  if [[ -e "$target_file" ]]; then
    echo "Keeping $target_file"
  else
    cp "$source_file" "$target_file"
    echo "Created $target_file"
  fi
done

mkdir -p .data restore
echo 'Edit .env, borgmatic/config.yaml, and docker-compose.yml, then run: docker compose up -d'

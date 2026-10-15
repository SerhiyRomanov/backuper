# Backuper

Backups run entirely through [docker-borgmatic](https://github.com/modem7/docker-borgmatic). Borgmatic handles files, database dumps, retention, repository checks, and restores; the image provides cron scheduling. No host Python installation or custom backup runner is needed.

## Prepare and run


Install Docker with Compose, then run:

```sh
./prepare.sh
```

This copies the examples below, creates local state directories, and preserves existing files on subsequent runs:

| Example | Your configuration |
| --- | --- |
| `.env.example` | `.env` |
| `docker-compose.example.yml` | `docker-compose.yml` |
| `borgmatic/config.yaml.example` | `borgmatic/config.yaml` |

Keep the repository passphrase and optional MySQL password in `.env`, quoted as in the example. The PostgreSQL password stays with its connection settings in `borgmatic/config.yaml`. Set the image version, timezone, and schedule directly in `docker-compose.yml`. The example pins Borgmatic 2.1.6 with Borg 1.4.5 for existing Borg 1 repositories.

Set your repository URL, source directories, retention, exclusions, and database connection settings in `borgmatic/config.yaml`. The host filesystem is mounted read-only at `/mnt/host`, so you can select multiple directories without changing Compose:

```yaml
source_directories:
  - /mnt/host/etc
  - /mnt/host/srv/application
  - /mnt/host/home
```

Only the listed directories are backed up. Exclusions use the same container paths. PostgreSQL connection settings, including its password, stay in the YAML; the optional MySQL example references its password from `.env`.

Compose uses `network_mode: bridge`, Docker's default network. Set the database hostname to its reachable IP address. The default bridge does not resolve container names; for name resolution, join the database's user-defined network instead. See [Docker's bridge network documentation](https://docs.docker.com/engine/network/drivers/bridge/). `localhost` refers to the backup container.

### SSH setup

Set up SSH manually before creating a repository or starting backups. The host's `/root/.ssh` is mounted read-only at `/root/.ssh` inside the container; SSH uses its default configuration and key filenames. `prepare.sh` only copies configuration files and creates local state directories.

Reuse an existing SSH key. If you do not have one, create a passwordless key for unattended backups:

```sh
sudo mkdir -p /root/.ssh
sudo chmod 700 /root/.ssh
sudo ssh-keygen -t ed25519 -N '' -f /root/.ssh/id_ed25519
```

Authorize the public key on the repository server:

```sh
sudo ssh-copy-id -s -i /root/.ssh/id_ed25519.pub -p 23 user@server.example.com
```

Use your repository's username, hostname, port, and key filename. Confirm the server's host-key fingerprint and enter its account password when prompted. The host key is saved in `/root/.ssh/known_hosts`. SFTP mode supports [Hetzner Storage Boxes](https://docs.hetzner.com/storage/storage-box/ssh-keys/add-ssh-keys/). Change the SSH mount in Compose if your host stores SSH files elsewhere.

### Start backups

For an existing repository, use its current passphrase and SSH key and start the container:

```sh
docker compose up -d
docker compose logs -f
```

For a **new** repository, create it before starting the service:

```sh
docker compose run --rm --entrypoint borgmatic borgmatic repo-create --encryption repokey
docker compose up -d
```

`CRON` in Compose controls the container's schedule (daily at 03:00 by default). Apply Compose or secret changes with `docker compose up -d`. Borgmatic reads the YAML configuration on each run. Additional configurations and schedules can use the image's native `EXTRA_CRON` support; see its documentation.

## Backup and restore

With the service running:

```sh
# Run a backup immediately.
docker compose exec borgmatic borgmatic create --stats --verbosity 1

# List archives and inspect one archive's sizes.
docker compose exec borgmatic borgmatic repo-list
docker compose exec borgmatic borgmatic info --archive latest

# Extract an archive into ./restore on the host.
docker compose exec borgmatic borgmatic extract --archive latest --destination /mnt/restore
```

Replace `latest` with an archive name to select a specific backup. Extraction may overwrite files in the destination. For database restores and other options, use the [Borgmatic documentation](https://torsion.org/borgmatic/).

Generated configuration files, local state, and restored files are ignored by Git. One mount, `./.data:/root`, preserves Borg configuration/cache and Borgmatic's check history at their default paths. The separate SSH mount supplies `/root/.ssh`. Keep `.data/` between container recreations. If you back up this project's directory, exclude `.env`, `.data/`, and `restore/` as appropriate.

The example's stable `backuper-` archive prefix scopes retention to matching backups. Keep the prefix unique if multiple configurations share a repository.

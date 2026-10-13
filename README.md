# How to set up DB backups
1. Clone project on host machine, i.e into `/srv/backuper`
2. `cp EXAMPLE-config.yaml config.yaml`
3. Edit `config.yaml` to setup
4. Execute `sudo bash setup-job.sh config.yaml`

`setup-job.sh` uses Bash and `yq` to read configuration, with no embedded Python. It supports relative or absolute configuration paths and uses its own directory as the backup working directory. It installs dependencies, validates the schedule, installs the SSH public key, and initializes the Borg repository before publishing a root job in `/etc/cron.d/backuper-<id>`. Each configuration path has its own job file, with logs in the project's `logs` directory. Existing user crontabs are preserved. The script targets Debian-style cron with `crontab -n` validation; PostgreSQL backups also install `postgresql-client` and `pigz`.

If you used the old setup script, remove its backup entry from root's user crontab with `sudo crontab -e` once to avoid running both the old entry and the new job. Preserve any unrelated entries.

## Borg CLI

Requires Python 3, PyYAML, and Borg 1.x installed locally, plus access to the remote repository configured in the YAML file.

```sh
python3 borg_wrapper.py -h
python3 borg_wrapper.py ls
python3 borg_wrapper.py extract 2026-10-12-03-00-files ./restored
python3 borg_wrapper.py extract -h
python3 borg_wrapper.py -c /path/to/custom-config.yaml ls
```

The configuration defaults to `config.yaml` in the current working directory. Use `-c PATH` (or `--config PATH`) before the command to select another file.

`ls` shows archive names, creation dates, and human-readable original, compressed, and deduplicated sizes. Original size is the uncompressed data size; compressed size is the compressed data size before deduplication; deduplicated size is the stored data unique to that archive. Chunks can be shared across backups, so the deduplicated sizes do not add up to the repository's total storage. Listing sizes reads archive statistics and can take longer than listing names alone.

`extract` downloads and restores the selected archive into the destination folder, creating it if needed. Paths inside the archive are preserved; existing files at those paths may be overwritten.

The wrapper exposes individual Borg operations. Archive names and retention options are supplied explicitly:

```sh
python3 borg_wrapper.py init
python3 borg_wrapper.py init repokey borg-1.4
python3 borg_wrapper.py create documents ./documents ./notes.txt --exclude '*.tmp'
python3 borg_wrapper.py prune --keep-within 14d --keep-weekly 7 --keep-monthly 10
python3 borg_wrapper.py compact
```

## Backup workflows

```sh
python3 backup-files.py config.yaml
python3 backup-pg-db.py config.yaml
```

`backup-files.py` owns configured folder selection, exclusions, timestamped archive naming, and the create/prune/compact sequence. `backup-pg-db.py` owns the database dump, timestamped archive naming, temporary dump cleanup, and its create/prune/compact sequence. Both scripts pass `borg_prune_params` from the configuration to the wrapper explicitly.

`backup_config.py` loads YAML and builds the connection arguments. `BorgBackup` accepts `repository`, `private_key_path`, and `passphrase`; its methods receive explicit operation arguments and do not read workflow configuration. `ls()` returns archive statistics, which the CLI formats as a table.

The workflow commands `create_files_backup_from_config`, `create_files_backup`, and `prune_and_compact_backups` have been replaced by the backup scripts and the low-level `create`, `prune`, and `compact` commands above.

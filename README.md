# Backuper

Repository settings live under `general`. Named jobs live under `jobs`, each with `source`, `cron`, and source-specific `config`. See [EXAMPLE-config.yaml](EXAMPLE-config.yaml).

## Setup and usage

1. Clone the project onto your Debian/Ubuntu backup machine, for example `/srv/backuper`.
2. Copy `EXAMPLE-config.yaml` to `config.yaml` and configure your repository and jobs.
3. Run `sudo bash setup-job.sh config.yaml` to install dependencies, set up SSH, reuse an accessible Borg repository or initialize a new one, and install the schedule.

`setup-job.sh` is a short launcher that installs base packages and calls `setup_job.py`. Python reads the config, installs source-specific packages, sets up SSH, reuses or initializes the repository, and installs one `* * * * *` cron entry invoking `backuper.py`. Output is appended to `logs/backuper.log`. Each configuration path has its own managed `/etc/cron.d/backuper-<id>` file; other cron files and user crontabs are preserved. The job changes into the project directory and uses an absolute configuration path. Schedule edits take effect on the next invocation, without changing cron.

```sh
python3 backuper.py -h
python3 backuper.py                  # Run jobs due this minute
python3 backuper.py files            # Run one job immediately
python3 backuper.py -c other.yaml postgresql
```

The default config is `./config.yaml`, resolved relative to the caller. Backup paths are resolved from the project directory. PyYAML is the only Python dependency; the scheduler uses the standard library, without croniter. Setup installs Python 3, Borg, PyYAML, cron, and OpenSSH, plus `postgresql-client` and `pigz` when a PostgreSQL job is configured. `yq` is no longer needed. Docker must already be installed for container-based PostgreSQL dumps.

## Scheduling and locks

Use numeric five-field schedules: minute, hour, day-of-month, month, weekday. The matcher supports `*`, comma-separated lists, inclusive ranges, and steps such as `*/5` or `8-18/2`. Sunday is `0` or `7`; month and weekday names, `@` shortcuts, seconds, and year fields are not supported. If both day-of-month and weekday are restricted, either can match; literal `*` means unrestricted.

The runner evaluates schedules once using server local time and runs due jobs in configuration order. Each job takes a nonblocking file lock and skips if another invocation is already running or waiting for that job. Different jobs sharing a repository wait for its shared lock. Runtime locks are stored in `.locks`; leave those files in place while jobs run.

There are no background workers, scheduling history, catch-up, or retries. Calling the dispatcher again within the same minute can rerun a completed job. Malformed settings, import errors, and command failures raise normally and end the invocation. Subsequent cron invocations start normally.

## Sources and retention

- `files`: `include` lists files/folders and optional `exclude` lists Borg exclusion patterns.
- `postgresql`: uses `host`, `user`, `password`, `database`, and an existing `dump_dir`. `port` defaults to 5432; `docker_container` is optional. A Bash pipeline dumps the database and compresses it with `pigz`; `pipefail` stops upload when either command fails. The local dump is deleted only after successful upload. On failure, it remains for inspection and may be incomplete. Passwords are passed through the environment.

Use simple job names containing letters, digits, underscores, or hyphens. Archives are named `<job-name>.<timestamp>`, including microseconds. Each job inherits `general.borg_prune_params`; a job-level list replaces it. `[]` disables pruning and compaction. Retention is scoped to `<job-name>.*`, so archives from other jobs and the old naming scheme are preserved. Supply retention rules only, without additional archive filters.

To add a source, create `sources/<name>.py` with:

```python
def backup(borg, archive_name, config):
    borg.create(archive_name, config["include"])
```

The source handles its backup operation and temporary files. The runner handles names, locks, retention, and compaction. Importing a source must not run a backup. Install any new source's prerequisites separately; MySQL is not implemented.

## Borg CLI

The low-level wrapper reads repository settings from `general` and remains available independently:

```sh
python3 cli.py -h
python3 cli.py info
python3 cli.py ls
python3 cli.py -c other.yaml ls
python3 cli.py extract files.2026-10-14-03-00-00-000000 ./restored
python3 cli.py init
python3 cli.py create documents ./documents ./notes.txt --exclude '*.tmp'
python3 cli.py prune --keep-within 14d --glob-archives 'files.*'
python3 cli.py compact
```

`ls` shows names, dates, and original/compressed/deduplicated sizes. Shared chunks mean per-archive deduplicated figures do not add up to repository storage. `extract` creates the destination folder and preserves archived paths; matching existing files may be overwritten.

## Migration

The old flat format and standalone `backup-*.py` commands are removed. Move repository keys and retention defaults under `general`. Map `cron` to a files job and `cron_db` to PostgreSQL. Rename `include_folders`/`exclude_folders` to `include`/`exclude`, and database keys to the short names shown in the example. Existing archives remain accessible.

For an existing installation, rerun setup to replace its managed cron command with the minute entrypoint command; the configuration's job schedules are now interpreted in Python. If the original setup installed a backup entry in root's user crontab, remove only that old backup entry using `sudo crontab -e`, preserving unrelated entries.

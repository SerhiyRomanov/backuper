#!/usr/bin/env python3
"""Check job schedules once, or run one job immediately."""

import argparse
from datetime import datetime
import fcntl
import hashlib
import importlib
import os
from pathlib import Path

from backup_config import borg_connection, load_config
from cli import BorgBackup

PROJECT_DIR = Path(__file__).resolve().parent


def field_matches(expression, value, minimum, maximum):
    for part in expression.split(","):
        span, separator, step = part.partition("/")
        step = int(step) if separator else 1
        if span == "*":
            first, last = minimum, maximum
        elif "-" in span:
            first, last = map(int, span.split("-"))
        else:
            first = int(span)
            last = maximum if separator else first
        if value in range(first, last + 1, step):
            return True
    return False


def cron_matches(expression, now):
    minute, hour, day, month, weekday = expression.split()
    day_matches = field_matches(day, now.day, 1, 31)
    week_day = now.isoweekday() % 7
    weekday_matches = field_matches(weekday, week_day, 0, 7)
    if week_day == 0:
        weekday_matches = weekday_matches or field_matches(weekday, 7, 0, 7)
    calendar_matches = (
        day_matches and weekday_matches if "*" in (day, weekday)
        else day_matches or weekday_matches
    )
    return (
        field_matches(minute, now.minute, 0, 59)
        and field_matches(hour, now.hour, 0, 23)
        and field_matches(month, now.month, 1, 12)
        and calendar_matches
    )


def lock_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def run_job(name, job, general, borg, config_file):
    lock_dir = PROJECT_DIR / ".locks"
    lock_dir.mkdir(exist_ok=True)
    job_path = lock_dir / f"{lock_id(str(config_file))}-{name}.lock"
    with job_path.open("a") as job_lock:
        try:
            fcntl.flock(job_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"Job {name} skipped: already running or waiting for the repository.", flush=True)
            return
        with (lock_dir / f"repository-{lock_id(borg.repo)}.lock").open("a") as repository_lock:
            print(f"Job {name} waiting for the repository.", flush=True)
            fcntl.flock(repository_lock, fcntl.LOCK_EX)
            archive_name = f"{name}.{datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')}"
            print(f"Job {name} started: {archive_name}", flush=True)
            source = importlib.import_module(f"sources.{job['source']}")
            source.backup(borg, archive_name, job["config"])
            retention = job.get("borg_prune_params", general.get("borg_prune_params", []))
            if retention:
                borg.prune([*retention, "--glob-archives", f"{name}.*"])
                borg.compact()
            print(f"Job {name} completed: {archive_name}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default="config.yaml", help="YAML config (default: ./config.yaml)")
    parser.add_argument("job", nargs="?", help="run this job immediately; omit to check schedules")
    args = parser.parse_args(argv)
    config_file = Path(args.config).expanduser().resolve()
    os.chdir(PROJECT_DIR)
    config = load_config(config_file)
    general = config["general"]
    borg = BorgBackup(**borg_connection(general))
    jobs = {args.job: config["jobs"][args.job]} if args.job else config["jobs"]
    now = datetime.now()
    for name, job in jobs.items():
        if args.job or cron_matches(job["cron"], now):
            run_job(name, job, general, borg, config_file)
        else:
            print(f"Job {name} skipped: not scheduled for {now:%Y-%m-%d %H:%M}.", flush=True)


if __name__ == "__main__":
    main()

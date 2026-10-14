#!/usr/bin/env python3

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime

from backup_config import borg_connection, load_config


def format_size(size):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"):
        if size < 1024 or unit == "EiB":
            return f"{size:.2f} {unit}"
        size /= 1024


class BorgBackup:
    """Low-level Borg operations with explicit connection and command arguments."""

    def __init__(self, repository, private_key_path, passphrase):
        self.repo = repository
        self.private_key_path = os.path.abspath(os.path.expanduser(private_key_path))
        self.borg_rsh = f"ssh -o IdentitiesOnly=yes -i {shlex.quote(self.private_key_path)}"

        # Add passphrase to environment variables
        self.env = {
            **os.environ,
            "BORG_PASSPHRASE": passphrase,
            "BORG_RSH": self.borg_rsh,
        }

    def run(self, args, cwd=None, capture_stdout=False):
        print(f"Running borg command: {shlex.join(['borg', *args])}", file=sys.stderr, flush=True)
        return subprocess.run(
            ["borg", *args],
            check=True,
            env=self.env,
            cwd=cwd,
            stdout=subprocess.PIPE if capture_stdout else None,
            text=True,
        )

    def init(self, encryption="repokey", remote_path="borg-1.4"):
        self.run(["init",
            f"--encryption={encryption}",
            f"--remote-path={remote_path}",
            self.repo
        ])

    def create(self, archive_name, paths, exclude=None, compression="zstd,3"):
        """Create an archive with the exact supplied name and paths."""
        if not paths:
            raise ValueError("At least one file or folder is required to create an archive.")
        exclusions = []
        for pattern in exclude or []:
            exclusions.extend(["--exclude", pattern])
        self.run(
            [
                "create", "-v", "--stats", "-C", compression,
                *exclusions, "--", f"{self.repo}::{archive_name}", *paths,
            ],
        )

    def prune(self, options):
        """Prune archives using explicitly supplied Borg retention options."""
        self.run(["prune", "-v", "--list", "--stats", *options, self.repo])

    def compact(self):
        """Reclaim repository space after archives have been removed."""
        self.run(["compact", "--progress", self.repo])

    def info(self):
        self.run(["info", self.repo])

    def ls(self):
        """List remote archives with their original, compressed, and unique sizes."""
        result = self.run(
            ["info", "--json", "--glob-archives", "*", "--sort-by", "timestamp", self.repo],
            capture_stdout=True,
        )
        return json.loads(result.stdout)["archives"]

    def extract(self, target_backup, target_folder):
        """Restore an archive into target_folder, preserving its stored paths."""
        target_folder = os.path.abspath(os.path.expanduser(target_folder))
        os.makedirs(target_folder, exist_ok=True)
        self.run(["extract", "--progress", f"{self.repo}::{target_backup}"], cwd=target_folder)


def print_archives(archives):
    """Format archive statistics for the CLI."""
    if not archives:
        print("No backups found.")
        return

    rows = [("BACKUP", "CREATED", "ORIGINAL", "COMPRESSED", "DEDUPLICATED")]
    for archive in archives:
        stats = archive["stats"]
        rows.append((
            archive["name"],
            datetime.fromisoformat(archive["start"]).strftime("%Y-%m-%d %H:%M:%S"),
            format_size(stats["original_size"]),
            format_size(stats["compressed_size"]),
            format_size(stats["deduplicated_size"]),
        ))

    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        print("  ".join(
            value.ljust(widths[index]) if index < 2 else value.rjust(widths[index])
            for index, value in enumerate(row)
        ))


def build_parser():
    parser = argparse.ArgumentParser(description="Manage backups in a configured Borg repository.")
    parser.add_argument(
        "-c", "--config", dest="config_file", default="config.yaml",
        help="path to the YAML configuration file (default: ./config.yaml)",
    )
    commands = parser.add_subparsers(dest="command", title="commands", required=True)

    init = commands.add_parser("init", help="initialize the repository")
    init.add_argument("encryption", nargs="?", default="repokey", help="encryption mode (default: repokey)")
    init.add_argument("remote_path", nargs="?", default="borg-1.4", help="remote Borg executable (default: borg-1.4)")

    create = commands.add_parser("create", help="create a named archive from specified files or folders")
    create.add_argument("archive_name", help="exact archive name (no automatic timestamp)")
    create.add_argument("paths", nargs="+", help="files or folders to back up")
    create.add_argument("-e", "--exclude", action="append", default=[], help="exclude a pattern (repeatable)")
    create.add_argument("-C", "--compression", default="zstd,3", help="compression mode (default: zstd,3)")

    prune = commands.add_parser("prune", help="prune archives using explicit retention rules")
    for rule in ("within", "last", "minutely", "hourly", "daily", "weekly", "monthly", "13weekly", "3monthly", "yearly"):
        prune.add_argument(f"--keep-{rule}", help=f"Borg --keep-{rule} retention setting")
    prune.add_argument("--glob-archives", help="only prune archive names matching this pattern")
    prune.add_argument("--dry-run", action="store_true", help="show pruning actions without deleting archives")
    commands.add_parser("compact", help="reclaim space after pruning archives")
    commands.add_parser("info", help="show repository information and verify access")
    commands.add_parser("ls", help="list remote backups with dates and sizes")
    extract = commands.add_parser("extract", help="download and restore a backup into a local folder")
    extract.add_argument("target_backup", help="archive name shown by ls")
    extract.add_argument("target_folder", help="destination folder (created if needed; existing files may be overwritten)")
    return parser


def main(argv=None):
    options = vars(build_parser().parse_args(argv))
    config_file = options.pop("config_file")
    command = options.pop("command")
    try:
        backup = BorgBackup(**borg_connection(load_config(config_file)["general"]))
        if command == "prune":
            dry_run = options.pop("dry_run")
            prune_options = [
                f"--{name.replace('_', '-')}={value}"
                for name, value in options.items() if value is not None
            ]
            if dry_run:
                prune_options.append("--dry-run")
            backup.prune(prune_options)
        elif command == "ls":
            print_archives(backup.ls())
        else:
            getattr(backup, command)(**options)
    except subprocess.CalledProcessError as error:
        print(f"Error: Borg exited with status {error.returncode}.", file=sys.stderr)
        return error.returncode
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

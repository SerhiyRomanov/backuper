#!/usr/bin/env python3

import os
import sys
import subprocess
import yaml
from datetime import datetime


class BorgBackup:
    def __init__(self, config_file):
        self.config_file = config_file
        with open(config_file, "r") as file:
            self.config_data = yaml.safe_load(file)

        self.repository_path = self.config_data.get("repository_path")
        self.repository_port = self.config_data.get("repository_port")
        self.repository_name = self.config_data.get("repository_name")
        self.private_key_path = self.config_data.get("private_key_path")
        self.repository_passphrase = self.config_data.get("repository_passphrase")

        if not all(
                [self.repository_path, self.repository_port, self.repository_name,
                 self.private_key_path, self.repository_passphrase]
        ):
            print("Error: Missing required configuration parameters in the config file.")
            sys.exit(1)

        self.repo = f"{self.repository_path}:{self.repository_port}/./{self.repository_name}"
        self.borg_rsh = f"ssh -o IdentitiesOnly=yes -i {self.private_key_path}"

        # Add passphrase to environment variables
        self.env = {
            "BORG_PASSPHRASE": self.repository_passphrase,
            "BORG_RSH": self.borg_rsh,
            **os.environ,  # Include existing environment variables
        }

    def run(self, *args):
        subprocess.run(
            ["borg", *args],
            check=True,
            env=self.env
        )

    def init(self, encryption="repokey", remote_path="borg-1.4"):
        self.run(
            "init",
            f"--encryption={encryption}",
            f"--remote-path={remote_path}",
            self.repo
        )

    def create_files_backup_from_config(self):
        include_folders = self.config_data.get("include_folders", [])
        exclude_folders = [
            f"--exclude {folder}" for folder in self.config_data.get("exclude_folders", [])
        ]

        self.run(
            [
                "create", "-v", "--stats", "-C", "zstd,3",
                f'{self.repo}::{datetime.now().strftime("%Y-%m-%d-%H-%M")}',
                *include_folders, *exclude_folders
            ],
        )

    def prune_and_compact_backups(self):
        borg_prune_params = self.config_data.get("borg_prune_params", [])

        # Prune backups
        self.run(["prune", "-v", "--list", "--stats", self.repo, *borg_prune_params])

        # Compact backups
        self.run(["compact", "--progress", self.repo])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <config_file> <method>")

        available_methods = [
            method for method in dir(BorgBackup) if
            callable(getattr(BorgBackup, method)) and not method.startswith("_")
        ]
        print("Available methods:", ", ".join(available_methods))
        sys.exit(1)

    config_file = sys.argv[1]
    backup = BorgBackup(config_file)
    method = sys.argv[2]

    args = []
    if len(sys.argv) > 3:
        args = sys.argv[3:]
        getattr(backup, method)(*args)

    getattr(backup, method)()

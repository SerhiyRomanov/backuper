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

    def create_files_backup_from_config(self):
        include_folders = self.config_data.get("include_folders", [])
        exclude_folders = [
            f"--exclude {folder}" for folder in self.config_data.get("exclude_folders", [])
        ]

        subprocess.run(
            [
                "borg", "create", "-v", "--stats", "-C", "zstd,3",
                f'{self.repo}::{datetime.now().strftime("%Y-%m-%d-%H-%M")}',
                *include_folders, *exclude_folders
            ],
            check=True,
            env=self.env
        )

    def prune_and_compact_backups(self):
        borg_prune_params = self.config_data.get("borg_prune_params", [])

        # Prune backups
        subprocess.run(
            ["borg",  "prune", "-v", "--list", "--stats", self.repo, *borg_prune_params],
            check=True,
            env=self.env,
        )

        # Compact backups
        subprocess.run(
            [
                "borg", "compact", "--progress", self.repo
            ],
            check=True,
            env=self.env
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config_file> <borg_arguments>")
        sys.exit(1)

    config_file = sys.argv[1]
    borg_arguments = sys.argv[2:]  # Remaining arguments are for Borg

    backup = BorgBackup(config_file)

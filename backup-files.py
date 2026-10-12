#!/usr/bin/env python3

import sys
from datetime import datetime

from backup_config import borg_connection, load_config
from borg_wrapper import BorgBackup


def create_files_backup_from_config(borg, config):
    archive_name = f'{datetime.now().strftime("%Y-%m-%d-%H-%M")}-files'
    borg.create(
        archive_name,
        config.get("include_folders", []),
        exclude=config.get("exclude_folders", []),
    )


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]

    print(f"###### Backup started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ######")

    config = load_config(config_file)
    borg = BorgBackup(**borg_connection(config))

    # Transfer files
    print("Transfer files ...")
    create_files_backup_from_config(borg, config)

    borg.prune(config.get("borg_prune_params", []))
    borg.compact()

    print(f"###### Backup ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ######")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import sys
from datetime import datetime

from borg_wrapper import BorgBackup

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]

    print(f"###### Backup started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ######")

    borg = BorgBackup(config_file)

    # Transfer files
    print("Transfer files ...")
    borg.create_files_backup_from_config()

    borg.prune_and_compact_backups()

    print(f"###### Backup ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ######")

if __name__ == "__main__":
    main()

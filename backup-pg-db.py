import os
import sys
import subprocess
from datetime import datetime

import yaml

from borg_wrapper import BorgBackup

if len(sys.argv) < 2:
    print("Usage: python script.py <config_file>")
    sys.exit(1)

config_file = sys.argv[1]

# Read configuration values
with open(config_file, 'r') as file:
    config = yaml.safe_load(file)

DB_DOCKER_CONTAINER_NAME = config.get('db_docker_container_name', None)
DB_HOST = config['db_host']
DB_PORT = config['db_port']
DB_USER = config['db_user']
DB_PASSWORD = config['db_password']
DB_NAME = config['db_name']
DB_BACKUP_LOCAL_DIR = config['db_backup_local_dir']

# Local Backup
LOCAL_BACKUP_FILE = f"{DB_BACKUP_LOCAL_DIR}{DB_NAME}-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.sql.gz"

DOCKER_COMMAND = f"docker exec -i {DB_DOCKER_CONTAINER_NAME}" if DB_DOCKER_CONTAINER_NAME else ""

NUM_PROCESSORS = os.cpu_count() - 1
if NUM_PROCESSORS < 1:
    NUM_PROCESSORS = 1

# Perform the database dump and compress it
pg_dump_command = (
    f"{DOCKER_COMMAND} "
    f"pg_dump -U {DB_USER} -h {DB_HOST} -p {DB_PORT} -c {DB_NAME} | "
    f"pigz --best -p{NUM_PROCESSORS} > {LOCAL_BACKUP_FILE}"
)
print(f"pg_dump command: {pg_dump_command}")

# add password
pg_dump_command = f"PGPASSWORD={DB_PASSWORD} " + pg_dump_command

subprocess.run(pg_dump_command, shell=True, check=True, capture_output=True)

# Get and print the size of the LOCAL_BACKUP_FILE
backup_file_size = os.path.getsize(LOCAL_BACKUP_FILE) / (1024 * 1024)
print(f"The size of the backup file '{LOCAL_BACKUP_FILE}' is {backup_file_size:.2f} MB.")

# Transfer the backup file to the remote server
borg = BorgBackup(config_file)
borg.create_files_backup("postgesql", [LOCAL_BACKUP_FILE])

# Remove the local backup file
os.remove(LOCAL_BACKUP_FILE)

borg.prune_and_compact_backups()

print("Backup completed successfully.")

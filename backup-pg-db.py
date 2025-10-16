import os
import sys
import subprocess
from datetime import datetime

import yaml

if len(sys.argv) < 2:
    print("Usage: python script.py <config_file>")
    sys.exit(1)

CONFIG_FILE = sys.argv[1]

# Read configuration values
with open(CONFIG_FILE, 'r') as file:
    config = yaml.safe_load(file)

PRIVATE_KEY_PATH = config['private_key_path']
DB_DOCKER_CONTAINER_NAME = config.get('db_docker_container_name', None)
DB_HOST = config['db_host']
DB_PORT = config['db_port']
DB_USER = config['db_user']
DB_PASSWORD = config['db_password']
DB_NAME = config['db_name']
DB_BACKUP_LOCAL_DIR = config['db_backup_local_dir']
DB_BACKUP_REMOTE = config['db_backup_remote']
DB_BACKUP_REMOTE_FOLDER = config['db_backup_remote_folder']
DB_BACKUP_KEEP_WITHIN = config['db_backup_keep_within']

# Local Backup
LOCAL_BACKUP_FILE = f"{DB_BACKUP_LOCAL_DIR}{DB_NAME}-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.sql.gz"

DOCKER_COMMAND = f"docker exec -i {DB_DOCKER_CONTAINER_NAME}" if DB_DOCKER_CONTAINER_NAME else ""

NUM_PROCESSORS = os.cpu_count() - 1
if NUM_PROCESSORS < 1:
    NUM_PROCESSORS = 1

# Perform the database dump and compress it
pg_dump_command = (
    f"PGPASSWORD={DB_PASSWORD} {DOCKER_COMMAND} "
    f"pg_dump -U {DB_USER} -h {DB_HOST} -p {DB_PORT} -c {DB_NAME} | "
    f"pigz --best -p{NUM_PROCESSORS} > {LOCAL_BACKUP_FILE}"
)
subprocess.run(pg_dump_command, shell=True, check=True)

# Transfer the backup file to the remote server
scp_command = f"scp -v -i {PRIVATE_KEY_PATH} {LOCAL_BACKUP_FILE} {DB_BACKUP_REMOTE}"
subprocess.run(scp_command, shell=True, check=True)

# Remove the local backup file
os.remove(LOCAL_BACKUP_FILE)

# Cleanup Remote Backups (list files)
print("List of backup files on remote server:")
list_remote_files_command = (
    f"ssh -i {PRIVATE_KEY_PATH} {DB_BACKUP_REMOTE} "
    f"'find -type f -name \"*.sql.gz\"'"
)
subprocess.run(list_remote_files_command, shell=True, check=True)

#!/usr/bin/env python3
import os
import subprocess
import logging
import sys
from pathlib import Path
from datetime import datetime
import yaml

from config_loader import load_config


def setup_logger(log_path: str) -> logging.Logger:
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("db-backuper")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(str(log_file))
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger

def run_pg_dump(cfg: dict, date_str: str, backup_folder: Path, logger: logging.Logger) -> Path:
    db = cfg["db"]
    out_file = backup_folder / f"{date_str}-{db['name']}.sql.gz"

    pg_dump_cmd = [
        "pg_dump",
        "-U", db["user"],
        "-h", db.get("host", "127.0.0.1"),
        "-p", str(db.get("port", 5432)),
        "-c",
        db["name"]
    ]

    if db.get("container_name"):
        cmd = ["docker", "exec", "-i", db["container_name"]] + pg_dump_cmd
        logger.info(f"Running pg_dump inside container '{db['container_name']}'")
        env = None  # password must be inside container env or .pgpass inside container
    else:
        cmd = pg_dump_cmd
        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("password", "")

    logger.info("pg_dump command: " + " ".join(cmd))
    with out_file.open("wb") as f:
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
        p2 = subprocess.Popen(["pigz", "--best", "-p2"], stdin=p1.stdout, stdout=f)
        p1.stdout.close()
        p2.communicate()

    logger.info(f"DB dump completed: {out_file}")
    return out_file

def main():
    if len(sys.argv) != 2:
        print("Usage: db_backup.py /path/to/config.yaml")
        sys.exit(1)
    cfg_path = sys.argv[1]
    cfg = load_config(cfg_path)
    log_file = cfg.get("log_file", "/var/log/backuper/backup.log")
    logger = setup_logger(log_file)

    if not cfg.get("db", {}).get("enabled", True):
        logger.info("DB backup disabled in config. Exiting.")
        return

    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_folder = Path(cfg.get("backup_folder", "/var/backups"))
    backup_folder.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Starting DB backup")
        run_pg_dump(cfg, date_str, backup_folder, logger)
        logger.info("DB backup finished")
    except Exception as e:
        logger.exception("DB backup failed: %s", e)
        # attempt to send email via backup.py's send function? (not imported here)
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Set up SSH, a Borg repository, and the minute cron entry."""

import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from backup_config import borg_connection, load_config
from cli import BorgBackup

PROJECT_DIR = Path(__file__).resolve().parent
CRON_DIR = Path("/etc/cron.d")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_file", help="YAML configuration file")
    args = parser.parse_args(argv)
    config_file = Path(args.config_file).expanduser().resolve()
    os.chdir(PROJECT_DIR)
    config = load_config(config_file)
    general = config["general"]

    if any(job["source"] == "postgresql" for job in config["jobs"].values()):
        print("[+] Installing PostgreSQL dependencies", flush=True)
        subprocess.run(["apt-get", "install", "-y", "postgresql-client", "pigz"], check=True)

    print("[+] Installing SSH public key", flush=True)
    subprocess.run([
        "ssh-copy-id", "-i", str(Path(general["private_key_path"]).expanduser().resolve()),
        "-p", str(general["repository_port"]), "-s", general["repository_path"].removeprefix("ssh://"),
    ], check=True)

    borg = BorgBackup(**borg_connection(general))
    print("[+] Checking Borg repository", flush=True)
    try:
        borg.info()
    except subprocess.CalledProcessError:
        print("[+] Initializing Borg repository", flush=True)
        borg.init()
    else:
        print("[+] Using existing Borg repository", flush=True)

    log_dir = PROJECT_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    command = (
        f"cd {shlex.quote(str(PROJECT_DIR))} && "
        f"{shlex.join([sys.executable, str(PROJECT_DIR / 'backuper.py'), '-c', str(config_file)])} "
        f">> {shlex.quote(str(log_dir / 'backuper.log'))} 2>&1"
    ).replace("%", r"\%")
    job_id = hashlib.sha256(str(config_file).encode()).hexdigest()[:16]
    cron_file = CRON_DIR / f"backuper-{job_id}"
    print(f"[+] Installing cron job: {cron_file}", flush=True)
    CRON_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=CRON_DIR, prefix=".backuper-", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(
                "# Managed by backuper setup_job.py\n"
                "SHELL=/bin/sh\n"
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
                f"* * * * * root {command}\n"
            )
            temporary.flush()
            os.fchown(temporary.fileno(), 0, 0)
            os.fchmod(temporary.fileno(), 0o644)
            temporary_path.replace(cron_file)
        finally:
            temporary_path.unlink(missing_ok=True)
    print(f"Done. Backup scheduled in {cron_file}; user crontabs were not modified.", flush=True)


if __name__ == "__main__":
    main()

"""Dump PostgreSQL, compress it, and create a Borg archive."""

import os
import shlex
import subprocess
import tempfile


def backup(borg, archive_name, config):
    command = [
        "pg_dump", "-h", config["host"], "-p", str(config.get("port", 5432)),
        "-U", config["user"], "-c", config["database"],
    ]
    if config.get("docker_container"):
        command = ["docker", "exec", "-i", "-e", "PGPASSWORD", config["docker_container"], *command]
    with tempfile.NamedTemporaryFile(
        dir=os.path.expanduser(config["dump_dir"]), prefix=f"{archive_name}.", suffix=".sql.gz", delete=False,
    ) as dump:
        dump_path = dump.name
    print(f"Dumping PostgreSQL to {dump_path}", flush=True)
    subprocess.run(
        ["bash", "-o", "pipefail", "-c", f"{shlex.join(command)} | pigz --best > {shlex.quote(dump_path)}"],
        env={**os.environ, "PGPASSWORD": config["password"]}, check=True,
    )
    borg.create(archive_name, [dump_path])
    os.remove(dump_path)

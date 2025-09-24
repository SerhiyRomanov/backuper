#!/usr/bin/env python3
import sys
import subprocess
import shutil
import logging
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime, timedelta
import yaml

from config_loader import load_config


# ----------------- logger setup -----------------
def setup_logger(log_path: str) -> logging.Logger:
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pg-backuper")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # File handler
    fh = logging.FileHandler(str(log_file))
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Stream handler (stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger

# ----------------- email notifier -----------------
def send_failure_email(cfg: dict, subject: str, body: str, logger: logging.Logger):
    notif = cfg.get("notifications") or {}
    emails = notif.get("emails")
    if not emails:
        logger.info("No notification emails configured; skipping email send.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = notif.get("from_email") or "backup@example.com"
    msg["To"] = ", ".join(emails)

    try:
        logger.info(f"Sending failure email to: {', '.join(emails)}")
        server = smtplib.SMTP(notif["smtp_server"], notif["smtp_port"], timeout=30)
        server.starttls()
        server.login(notif["smtp_user"], notif["smtp_password"])
        server.sendmail(msg["From"], emails, msg.as_string())
        server.quit()
        logger.info("Failure email sent.")
    except Exception as e:
        logger.exception(f"Failed to send notification email: {e}")

# ----------------- archive -----------------
def create_archive(cfg: dict, date_str: str, backup_dir: Path, logger: logging.Logger) -> Path:
    includes = cfg.get("files", {}).get("includes", [])
    excludes = cfg.get("files", {}).get("excludes", [])
    out_path = backup_dir / f"{date_str}-backend.tar.gz"

    # Build safe shell pipeline: tar -> pigz
    exclude_flags = " ".join(f"--exclude='{e}'" for e in excludes)
    include_list = " ".join(f"'{p}'" for p in includes)
    tar_cmd = f"tar {exclude_flags} -cf - {include_list}| pigz --best -p$(nproc) > '{out_path}'"

    logger.info("Creating archive (tar -> pigz)...")
    logger.info("Running: " + tar_cmd)
    subprocess.run(tar_cmd, shell=True, check=True, executable="/bin/bash")
    logger.info(f"Archive created: {out_path}")
    return out_path

# ----------------- copy/upload -----------------
def upload_or_copy(cfg: dict, local_path: Path, logger: logging.Logger):
    target = cfg.get("target_backup_folder")
    if target:
        dest = Path(target)
        dest.mkdir(parents=True, exist_ok=True)
        logger.info(f"Copying {local_path.name} -> {dest}")
        shutil.copy2(local_path, dest / local_path.name)
        logger.info("Copy completed.")
    else:
        ftp = cfg.get("ftp") or {}
        user = ftp.get("user")
        host = ftp.get("host")
        remote_dir = ftp.get("remote_dir", ".")
        if not (user and host):
            logger.error("FTP destination not configured (ftp.user/ftp.host). Skipping upload.")
            return
        remote = f"{user}@{host}:{remote_dir}"
        logger.info(f"Uploading {local_path.name} to {remote} via scp")
        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", str(local_path), remote], check=True)
        logger.info("Upload completed.")

# ----------------- cleanup retention -----------------
def remove_old_backups(backup_dir: Path, days: int, logger: logging.Logger):
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    size_removed = 0
    logger.info(f"Removing backups older than {days} days (cutoff={cutoff.isoformat()})")
    for f in backup_dir.iterdir():
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                logger.info(f"Removing old file: {f.name}")
                size_removed += f.stat().st_size
                f.unlink()
                removed += 1
    logger.info(f"Removed {removed} files, freed {(size_removed/1024**2):.2f} MB")

# ----------------- summary -----------------
def summarize(backup_dir: Path, logger: logging.Logger):
    files = [f for f in backup_dir.iterdir() if f.is_file()]
    total_size = sum(f.stat().st_size for f in files)
    logger.info(f"Summary: {len(files)} files, total size {(total_size/1024**2):.2f} MB")
    for f in files:
        logger.info(f" - {f.name} ({(f.stat().st_size/1024**2):.2f} MB)")

# ----------------- main -----------------
def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    cfg = load_config(cfg_path)
    log_file = cfg.get("log_file", "/var/log/backuper/backup.log")
    logger = setup_logger(log_file)

    backup_folder = Path(cfg.get("backup_folder", "/var/backups"))
    backup_folder.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")

    try:
        logger.info("=== Backup run started ===")
        # Optionally run DB dump if enabled and container wants to do it here
        if cfg.get("db", {}).get("enabled") and cfg["db"].get("run_in_backup_container", False):
            # If you want the container to run pg_dump itself, implement here
            logger.info("DB dump inside backup container requested (not implemented in this snippet).")

        # Create archive
        tar_path = create_archive(cfg, date_str, backup_folder, logger)

        # Transfer files (either copy to target or scp)
        upload_or_copy(cfg, tar_path, logger)

        # Retention cleanup
        remove_old_backups(backup_folder, cfg.get("retention_days", 7), logger)

        summarize(backup_folder, logger)
        logger.info("=== Backup run finished successfully ===")

    except Exception as e:
        logger.exception("Backup run failed: %s", e)
        try:
            send_failure_email(cfg, "[Backup Failure] pg-backuper failed", str(e), logger)
        except Exception:
            logger.exception("Failed sending failure email")
        sys.exit(1)

if __name__ == "__main__":
    main()

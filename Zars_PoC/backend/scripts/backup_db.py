import os
import subprocess
import sys
from datetime import datetime

# Rabta AI Automated Database Backup Utility
# Backs up the PostgreSQL database to a timestamped .sql / .dump file and prunes old backups

PG_DUMP_PATH = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
DB_NAME = "rabta_dev"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"
PG_PASSWORD = "abc123"

BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))


def run_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"rabta_dev_backup_{timestamp}.sql")

    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD

    cmd = [
        PG_DUMP_PATH,
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "-F", "p",  # plain SQL format
        "-f", backup_file,
    ]

    print(f"[*] Starting PostgreSQL backup for '{DB_NAME}' -> {backup_file}...")
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        size = os.path.getsize(backup_file)
        print(f"[+] Backup completed successfully! File size: {size:,} bytes")
        prune_old_backups(max_days=7)
        return backup_file
    except subprocess.CalledProcessError as e:
        print(f"[!] Backup failed: {e.stderr}")
        sys.exit(1)


def prune_old_backups(max_days: int = 7):
    """Keep backups clean by removing dumps older than max_days."""
    now = datetime.now().timestamp()
    count = 0
    for fname in os.listdir(BACKUP_DIR):
        if fname.startswith("rabta_dev_backup_") and fname.endswith(".sql"):
            fpath = os.path.join(BACKUP_DIR, fname)
            mtime = os.path.getmtime(fpath)
            if now - mtime > (max_days * 86400):
                os.remove(fpath)
                count += 1
    if count:
        print(f"[*] Pruned {count} backups older than {max_days} days.")


if __name__ == "__main__":
    run_backup()

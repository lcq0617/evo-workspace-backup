#!/usr/bin/env python3
"""scripts/safe_iter.py

Safe iteration wrapper:
- Creates a safe git-backed snapshot (commit) before running a potentially dangerous command.
- Runs the command streaming output to stdout/stderr.
- If the command exits non-zero, automatically rolls back to the snapshot commit.

Usage: python scripts/safe_iter.py <command> [args...]
"""

import sys
import os
import shlex
import time
import json
import shutil
import subprocess
from pathlib import Path

RED = "\033[1;31m"
RESET = "\033[0m"
BACKUP_RECORD_DIR = ".backups"


def run_cmd_stream(cmd):
    """Run a command streaming stdout/stderr, return exit code."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # stream output
        for line in proc.stdout:
            print(line, end="")
        proc.wait()
        return proc.returncode
    except FileNotFoundError:
        print(f"{RED}命令未找到: {cmd[0]}{RESET}", file=sys.stderr)
        return 127
    except Exception as e:
        print(f"{RED}运行命令时发生异常: {e}{RESET}", file=sys.stderr)
        return 1


def git_backup_commit(message):
    """Stage all changes and create a commit; return commit hash or (None, error)."""
    os.makedirs(BACKUP_RECORD_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    # Stage changes
    rc = subprocess.call(["git", "add", "-A"])  # respect .gitignore
    if rc != 0:
        return None, "git add failed"
    # Commit
    commit_msg = f"{message} [{ts}]"
    rc = subprocess.call(["git", "commit", "-m", commit_msg])
    if rc != 0:
        return None, "git commit failed (nothing to commit or error)"
    # Get commit hash
    res = subprocess.run(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True)
    commit_hash = res.stdout.strip()
    # Record backup
    rec = {"ts": ts, "commit": commit_hash, "msg": message}
    path = Path(BACKUP_RECORD_DIR) / f"{ts}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return commit_hash, None


def do_rollback_to(commit_hash):
    """Rollback to given commit hash (hard) and clean untracked files."""
    print(f"{RED}检测到致命异常，触发自动回滚到 {commit_hash}！{RESET}", file=sys.stderr)
    subprocess.call(["git", "reset", "--hard", commit_hash])
    subprocess.call(["git", "clean", "-fd"])


def try_use_just_backup(message):
    """Attempt to call 'just backup <msg>' and return commit hash if successful, else None."""
    if shutil.which("just") is None:
        return None
    rc = subprocess.call(["just", "backup", message])
    if rc != 0:
        return None
    # get HEAD
    res = subprocess.run(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True)
    return res.stdout.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: safe_iter.py <command> [args...]", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1:]
    cmd_display = " ".join(shlex.quote(c) for c in cmd)
    backup_msg = f"Auto-backup before running: {cmd_display}"

    # Try just first
    commit_hash = try_use_just_backup(backup_msg)

    if not commit_hash:
        commit_hash, err = git_backup_commit(backup_msg)
        if not commit_hash:
            print(f"{RED}自动备份失败：{err}. 中止执行。{RESET}", file=sys.stderr)
            sys.exit(1)

    # Run the command
    rc = run_cmd_stream(cmd)
    if rc != 0:
        do_rollback_to(commit_hash)
        # Optional post-rollback checks could go here
        sys.exit(rc)
    print("Command completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()

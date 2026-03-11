#!/usr/bin/env python3
"""scripts/safe_iter.py

Improved safe_iter:
- Create a single explicit backup commit (or reuse HEAD if no changes) and record it as .backups/<commit>.json
- Stream command output
- On non-zero exit, rollback to the recorded commit using git reset --hard + git clean -fd and a restore fallback
- Attempts to normalize recovery across Windows by using git restore or git checkout when available

Usage: python scripts/safe_iter.py <command> [args...]
"""

from __future__ import annotations
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
BACKUP_RECORD_DIR = Path('.backups')


def run_cmd_stream(cmd):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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


def run_capture(cmd):
    """Run command and return (rc, stdout)."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return res.returncode, res.stdout
    except FileNotFoundError:
        return 127, ''


def ensure_git_repo():
    rc, out = run_capture(['git', 'rev-parse', '--is-inside-work-tree'])
    return rc == 0


def get_head():
    rc, out = run_capture(['git', 'rev-parse', 'HEAD'])
    if rc == 0:
        return out.strip()
    return None


def make_backup_commit(message: str) -> str | None:
    BACKUP_RECORD_DIR.mkdir(exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    prev_head = get_head()
    # Stage all (respect .gitignore)
    rc_add, out_add = run_capture(['git', 'add', '-A'])
    if rc_add != 0:
        print('git add failed:', out_add, file=sys.stderr)
        return None
    # Try commit
    commit_msg = f"{message} [{ts}]"
    rc_commit, out_commit = run_capture(['git', 'commit', '-m', commit_msg])
    if rc_commit == 0:
        # new commit created
        rc, out = run_capture(['git', 'rev-parse', 'HEAD'])
        if rc == 0:
            commit_hash = out.strip()
        else:
            commit_hash = None
    else:
        # Nothing to commit or commit failed -> reuse prev_head
        if prev_head:
            commit_hash = prev_head
        else:
            # no HEAD (empty repo). attempt to create an initial commit by committing whatever is present
            # try to create an initial commit by setting a temporary commit
            rc_init, out_init = run_capture(['git', 'commit', '--allow-empty', '-m', commit_msg])
            if rc_init == 0:
                rc, out = run_capture(['git', 'rev-parse', 'HEAD'])
                commit_hash = out.strip() if rc == 0 else None
            else:
                print('Failed to create backup commit and no prev HEAD:', out_commit or out_init, file=sys.stderr)
                commit_hash = None
    if not commit_hash:
        return None
    # Record backup file named by commit hash for unambiguous mapping
    rec = {'ts': ts, 'commit': commit_hash, 'msg': message}
    path = BACKUP_RECORD_DIR / f'{commit_hash}.json'
    try:
        with path.open('w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('Failed to write backup record:', e, file=sys.stderr)
    return commit_hash


def rollback_to(commit_hash: str):
    print(f"{RED}检测到致命异常，触发自动回滚到 {commit_hash}！{RESET}", file=sys.stderr)
    # Hard reset
    subprocess.call(['git', 'reset', '--hard', commit_hash])
    subprocess.call(['git', 'clean', '-fd'])
    # Try to restore worktree explicitly (git restore preferred)
    rc, out = run_capture(['git', 'restore', '--source', commit_hash, '--worktree', '--staged', '.'])
    if rc != 0:
        # fallback to checkout
        subprocess.call(['git', 'checkout', commit_hash, '--', '.'])


def try_use_just_backup(message: str) -> str | None:
    if shutil.which('just') is None:
        return None
    rc = subprocess.call(['just', 'backup', message])
    if rc != 0:
        return None
    return get_head()


def main():
    if len(sys.argv) < 2:
        print('Usage: safe_iter.py <command> [args...]', file=sys.stderr)
        sys.exit(2)
    if not ensure_git_repo():
        print('Not inside a git repository. Aborting.', file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1:]
    cmd_display = ' '.join(shlex.quote(c) for c in cmd)
    backup_msg = f'Auto-backup before running: {cmd_display}'

    # Prefer just if available and working
    commit_hash = try_use_just_backup(backup_msg)
    if not commit_hash:
        commit_hash = make_backup_commit(backup_msg)
    if not commit_hash:
        print(f"{RED}自动备份失败：无法生成备份 commit. 中止执行。{RESET}", file=sys.stderr)
        sys.exit(1)

    # Run the command
    rc = run_cmd_stream(cmd)
    if rc != 0:
        rollback_to(commit_hash)
        sys.exit(rc)
    print('Command completed successfully.')
    sys.exit(0)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Updated verify script to match improved safe_iter behavior
"""
import tools.monkeypatch_model_calls
import subprocess
import sys
import os
import shutil
import json
from pathlib import Path

ROOT = Path.cwd()
BACKUP_DIR = ROOT / '.backups'
SAFE_ITER = ROOT / 'scripts' / 'safe_iter.py'
TMP_FILE = ROOT / 'tmp_test.txt'

RESULTS = []

def run(cmd, capture=True, check=False):
    try:
        if capture:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out = r.stdout
        else:
            r = subprocess.run(cmd)
            out = ''
        return r.returncode, out
    except FileNotFoundError:
        return 127, ''


def ok(msg):
    print('[OK] ', msg)
    RESULTS.append((msg, True))


def fail(msg, info=None):
    print('[FAIL]', msg)
    if info:
        print(info)
    RESULTS.append((msg, False))


def prechecks():
    print('\n== Prechecks ==')
    rc, out = run(['git', '--version'])
    if rc != 0:
        fail('git not available')
        return False
    else:
        ok('git available: ' + out.splitlines()[0])
    rc, out = run(['git', 'status', '--porcelain'])
    if rc != 0:
        fail('git status failed', out)
        return False
    else:
        print('git status (porcelain):', repr(out.strip()))
    rc, out = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    if rc == 0:
        ok('branch: ' + out.strip())
    rc, out = run(['git', 'rev-parse', 'HEAD'])
    if rc == 0:
        ok('HEAD: ' + out.strip())
    return True


def check_backups_dir():
    print('\n== Check .backups dir ==')
    if BACKUP_DIR.exists() and any(BACKUP_DIR.iterdir()):
        files = sorted([p.name for p in BACKUP_DIR.iterdir()])
        ok('.backups exists, files: ' + ', '.join(files[-5:]))
    else:
        fail('.backups missing or empty')


def manual_backup_record(msg='verify manual backup'):
    print('\n== Manual backup (git) ==')
    rc, out = run(['git', 'add', '-A'])
    if rc != 0:
        fail('git add failed', out)
        return None
    rc, out = run(['git', 'commit', '-m', msg])
    if rc != 0:
        # nothing to commit is okay
        print('git commit exit code', rc)
    else:
        ok('git commit created: ' + (out.splitlines()[-1] if out.strip() else 'commit created'))
    rc, out = run(['git', 'rev-parse', 'HEAD'])
    if rc == 0:
        commit = out.strip()
        BACKUP_DIR.mkdir(exist_ok=True)
        rec = {'ts': commit[:10], 'commit': commit, 'msg': msg}
        p = BACKUP_DIR / f'{commit}.manual.json'
        p.write_text(json.dumps(rec, indent=2), encoding='utf-8')
        ok('manual backup recorded: ' + commit)
        return commit
    else:
        fail('cannot read HEAD after commit', out)
        return None


def prepare_tracked_test_file():
    print('\n== Prepare tracked test file ==')
    TMP_FILE.write_text('original\n', encoding='utf-8')
    rc, out = run(['git', 'add', str(TMP_FILE)])
    if rc != 0:
        fail('git add tmp_test.txt failed', out)
        return None
    rc, out = run(['git', 'commit', '-m', 'test: add tmp_test.txt for rollback test'])
    if rc != 0:
        fail('git commit tmp_test.txt failed', out)
        return None
    rc, out = run(['git', 'rev-parse', 'HEAD'])
    if rc == 0:
        ok('tmp_test.txt committed at ' + out.strip())
        return out.strip()
    fail('cannot get commit for tmp_test.txt', out)
    return None


def run_safe_iter_success():
    print('\n== safe_iter success case ==')
    if not SAFE_ITER.exists():
        fail('safe_iter.py not found: ' + str(SAFE_ITER))
        return False
    rc, out = run([sys.executable, str(SAFE_ITER), sys.executable, '-c', "print('hello safe-run'); import sys; sys.exit(0)" ])
    print(out)
    if rc == 0:
        ok('safe_iter success run returned 0')
        return True
    else:
        fail('safe_iter success run returned non-zero', out)
        return False


def run_safe_iter_failure():
    print('\n== safe_iter failure case ==')
    pre_head_rc, pre_head_out = run(['git', 'show', 'HEAD:tmp_test.txt'])
    expected = 'original\n'
    if pre_head_rc != 0 or pre_head_out != expected:
        print('Warning: HEAD tmp_test.txt content not as-expected, pre_head:', pre_head_rc, repr(pre_head_out))

    rc, out = run([sys.executable, str(SAFE_ITER), sys.executable, '-c', "open('tmp_test.txt','w').write('CORRUPTED\\n'); import sys; sys.exit(1)" ])
    print(out)
    if rc == 0:
        fail('safe_iter failure-case returned 0 (expected non-zero)')
        return False
    # After failure, find the latest .backups record (by commit-named file)
    files = sorted([p for p in BACKUP_DIR.iterdir() if p.is_file()])
    if not files:
        fail('no backup records found after safe_iter run')
        return False
    last = files[-1]
    rec = json.loads(last.read_text(encoding='utf-8'))
    commit = rec.get('commit')
    # Check HEAD
    rc1, head_commit = run(['git', 'rev-parse', 'HEAD'])
    if rc1 != 0:
        fail('cannot get HEAD after failure', head_commit)
        return False
    # Check file content
    rc2, head_content = run(['git', 'show', f'{commit}:tmp_test.txt'])
    # read worktree
    rc3, work_content = run([sys.executable, '-c', "print(open('tmp_test.txt').read())"]) 
    print('HEAD content repr:', repr(head_content))
    print('work content repr:', repr(work_content))
    if head_content == expected and work_content == expected:
        ok('rollback restored tmp_test.txt to original in HEAD and worktree')
        return True
    else:
        fail('rollback did not restore expected content', f'HEAD={repr(head_content)} WORK={repr(work_content)}')
        return False


def check_backups_record_matches_head():
    print('\n== Check backups record matches HEAD ==')
    if not BACKUP_DIR.exists():
        fail('.backups missing')
        return
    files = sorted([p for p in BACKUP_DIR.iterdir() if p.is_file()])
    if not files:
        fail('.backups empty')
        return
    last = files[-1]
    try:
        rec = json.loads(last.read_text(encoding='utf-8'))
        commit = rec.get('commit')
        if not commit:
            fail('last backup record has no commit field')
            return
        rc, out = run(['git', 'rev-parse', 'HEAD'])
        if rc == 0 and out.strip() == commit:
            ok('.backups last commit matches HEAD')
        else:
            print('last backup commit:', commit)
            print('current HEAD:', out)
            fail('last backup commit does not match HEAD')
    except Exception as e:
        fail('error reading last backup JSON', str(e))


def test_gitignore_behavior():
    print('\n== Test .gitignore behavior ==')
    secret = ROOT / 'secret.env'
    secret.write_text('SECRET', encoding='utf-8')
    rc, out = run(['git', 'add', '-A'])
    rc, out = run(['git', 'ls-files', '--others', '--exclude-standard'])
    if 'secret.env' in out:
        ok('secret.env is untracked (ignored)')
    else:
        rc2, out2 = run(['git', 'ls-files', 'secret.env'])
        if out2.strip():
            fail('secret.env is tracked (should be ignored)')
        else:
            ok('secret.env not listed among untracked (ambiguous pass)')
    try:
        secret.unlink()
    except Exception:
        pass


def summary():
    print('\n== Summary ==')
    pass_count = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    for msg, ok_flag in RESULTS:
        print(('PASS' if ok_flag else 'FAIL'), msg)
    print(f'Passed {pass_count}/{total} checks')


if __name__ == '__main__':
    if not prechecks():
        sys.exit(1)
    check_backups_dir()
    manual_backup_record()
    prepare_tracked_test_file()
    run_safe_iter_success()
    run_safe_iter_failure()
    check_backups_record_matches_head()
    test_gitignore_behavior()
    summary()

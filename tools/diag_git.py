"""
diag_git.py - diagnostic script for git remotes, status, and recent commits.
Prints JSON with: has_git, remotes, last_commits (5), status_porcelain, last_error (if any)
"""
import subprocess, json, sys

def run(cmd):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, check=False, text=True)
        return {'rc': p.returncode, 'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()}
    except Exception as e:
        return {'rc': 99, 'stdout': '', 'stderr': str(e)}

out = {}
# is this a git repo?
res = run(['git', 'rev-parse', '--is-inside-work-tree'])
if res['rc'] != 0:
    out['has_git'] = False
    out['last_error'] = res['stderr']
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0)
out['has_git'] = True

# remotes
rem = run(['git', 'remote', '-v'])
out['remotes_raw'] = rem

# remote origin url
origin = run(['git', 'config', '--get', 'remote.origin.url'])
out['origin_url'] = origin

# last commits
log = run(['git', 'log', '-n', '10', '--pretty=format:%h|%ad|%s', '--date=iso'])
out['last_commits_raw'] = log

# status
status = run(['git', 'status', '--porcelain'])
out['status_porcelain'] = status

# last commit show stat
show = run(['git', 'show', '--stat', '--pretty=format:%h %s', '-n', '1'])
out['last_commit_show'] = show

print(json.dumps(out, ensure_ascii=False, indent=2))

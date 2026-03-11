#!/usr/bin/env python3
"""scripts/init_git.py

Initialize git repository and configure remote with optional PAT.

Usage:
  python scripts/init_git.py --repo-url <repo-url> [--token <pat>] [--name "Evo Auto-Agent"] [--email "evo@localhost"]

If --token is provided (or GITHUB_TOKEN env var is set), the script will add the remote using the token embedded in the URL for a one-time push. Storing tokens in git config or remotes is a security tradeoff; prefer passing the token via environment when pushing or let the user run the push locally.
"""
import argparse
import os
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--repo-url', required=True, help='HTTPS repo URL, e.g. https://github.com/owner/repo.git')
parser.add_argument('--token', help='GitHub PAT (optional). If omitted, GITHUB_TOKEN env var will be used if set')
parser.add_argument('--name', default='Evo Auto-Agent')
parser.add_argument('--email', default='evo@localhost')
args = parser.parse_args()

def run(cmd):
    print('>',' '.join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f'Command failed: {cmd}', file=sys.stderr)
        sys.exit(rc)

# git init
run(['git', 'init'])
# config identity
run(['git', 'config', 'user.name', args.name])
run(['git', 'config', 'user.email', args.email])
# prepare remote
token = args.token or os.environ.get('GITHUB_TOKEN')
if token:
    # embed token into URL (https://<token>@github.com/owner/repo.git)
    if args.repo_url.startswith('https://'):
        url = args.repo_url.replace('https://', f'https://{token}@')
    else:
        url = args.repo_url
    # remove existing origin if present
    subprocess.call(['git', 'remote', 'remove', 'origin'])
    run(['git', 'remote', 'add', 'origin', url])
    print('\nWARNING: remote was added with token embedded in the URL. This stores credential info in your git config. Consider removing the token from remote afterwards and using a credential helper for pushes.')
else:
    subprocess.call(['git', 'remote', 'remove', 'origin'])
    run(['git', 'remote', 'add', 'origin', args.repo_url])

print('\nInitialization complete.')

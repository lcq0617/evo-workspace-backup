"""
Batch commit and push grouped changes: tools, scripts, docs.
Prints JSON result with per-step rc/stdout/stderr.

Run: python tools/_git_batch_commit_and_push.py
"""
import subprocess, json, sys, os

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {'rc': p.returncode, 'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
res = {'steps': []}

# Step A: tools/
resA = {'name':'A_tools','actions':[]}
resA['actions'].append(run(['git','add','tools']))
resA['actions'].append(run(['git','commit','-m','chore: add tools for prompt budget, scanner, monkeypatch and helpers']))
res['steps'].append(resA)

# Step B: scripts/ entry imports
scripts_to_add = ['scripts/compress_memory.py','scripts/learn.py','scripts/llm_guard.py','scripts/prompt_budget.py','scripts/safe_iter.py','scripts/verify_backup_rollback.py']
resB = {'name':'B_scripts','actions':[]}
# add only existing ones
for f in scripts_to_add:
    if os.path.exists(os.path.join(ROOT,f)):
        resB['actions'].append(run(['git','add',f]))
resB['actions'].append(run(['git','commit','-m','chore: auto-insert monkeypatch import into entry scripts to enable prompt budget enforcement']))
res['steps'].append(resB)

# Step C: docs/metadata
docs = ['IDENTITY.md','Justfile','MEMORY.md','SOUL.md','USER.md']
resC = {'name':'C_docs','actions':[]}
for f in docs:
    if os.path.exists(os.path.join(ROOT,f)):
        resC['actions'].append(run(['git','add',f]))
resC['actions'].append(run(['git','commit','-m','chore: update identity and memory files (automated)']))
res['steps'].append(resC)

# Final: push
res['push'] = run(['git','push','origin','HEAD'])

print(json.dumps(res, ensure_ascii=False, indent=2))

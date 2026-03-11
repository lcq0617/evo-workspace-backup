"""
find_prompts.py - scan the workspace for likely long prompts or model-call sites.
Outputs JSON lines with: path, line_number, preview, reason

Run: python tools/find_prompts.py
"""
import os
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDES = {'.git', 'node_modules', 'memory', '__pycache__', '.openclaw'}
TEXT_EXTS = {'.py', '.js', '.ts', '.json', '.md', '.txt', '.yaml', '.yml', '.html'}

def is_text_file(p: Path):
    return p.suffix.lower() in TEXT_EXTS

long_string_re = re.compile(r'(["\']{1,3})(.{200,}?)(\1)', re.S)
keywords = ['system', 'prompt', 'instruction', 'messages', 'task', 'sessions_spawn', 'openai', 'model=']

matches = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # skip excludes
    parts = set(Path(dirpath).parts)
    if parts & EXCLUDES:
        continue
    for fname in filenames:
        p = Path(dirpath) / fname
        if not is_text_file(p):
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            continue
        # search for long string literals
        for m in long_string_re.finditer(text):
            preview = m.group(2).replace('\n', '\\n')[:300]
            matches.append({'path': str(p.relative_to(ROOT)), 'line': text[:m.start()].count('\n')+1, 'preview': preview, 'reason': 'long_string_literal'})
        # search for keyword occurrences
        for kw in keywords:
            for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
                # record the line
                line_no = text[:m.start()].count('\n')+1
                line = text.splitlines()[line_no-1].strip() if line_no-1 < len(text.splitlines()) else ''
                matches.append({'path': str(p.relative_to(ROOT)), 'line': line_no, 'preview': line[:300], 'reason': f'keyword:{kw}'})

# dedupe by path+line+reason
seen = set()
out = []
for m in matches:
    key = (m['path'], m['line'], m['reason'])
    if key in seen: continue
    seen.add(key)
    out.append(m)

# sort by path then line
out.sort(key=lambda x: (x['path'], x['line']))
print(json.dumps(out, ensure_ascii=False, indent=2))

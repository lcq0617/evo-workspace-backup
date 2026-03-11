"""
Insert a top-level import of tools.monkeypatch_model_calls into python entry scripts.
Rules:
- Scan .py files (excluding tools/ and .git/ and venv-like dirs).
- If file contains "if __name__ == '__main__'" and does not already import tools.monkeypatch_model_calls, insert the import near the top:
  - Preserve shebang and encoding and module docstring.
- Print JSON list of modified files.
"""
from pathlib import Path
import re
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {'.git', 'venv', 'env', '__pycache__', 'tools'}
PAT_MAIN = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
IMPORT_LINE = 'import tools.monkeypatch_model_calls\n'

modified = []
for p in ROOT.rglob('*.py'):
    parts = set(p.parts)
    if parts & EXCLUDE_DIRS:
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue
    if PAT_MAIN.search(text) and 'tools.monkeypatch_model_calls' not in text:
        lines = text.splitlines(keepends=True)
        insert_at = 0
        # skip shebang
        if lines and lines[0].startswith('#!'):
            insert_at = 1
        # skip encoding declaration
        if len(lines) > insert_at and re.match(r"#.*coding[:=]", lines[insert_at]):
            insert_at += 1
        # skip module docstring
        if len(lines) > insert_at and re.match(r"\s*[ruRU]?['\"]{3}", lines[insert_at]):
            # find end of docstring
            end_idx = None
            quote = lines[insert_at].lstrip()[:3]
            for i in range(insert_at+1, len(lines)):
                if quote in lines[i]:
                    end_idx = i
                    break
            if end_idx is None:
                insert_at = insert_at + 1
            else:
                insert_at = end_idx + 1
        # perform insertion
        lines.insert(insert_at, IMPORT_LINE)
        try:
            p.write_text(''.join(lines), encoding='utf-8')
            modified.append(str(p.relative_to(ROOT)))
        except Exception as e:
            print(json.dumps({'error': str(e), 'path': str(p)}))

print(json.dumps({'modified': modified}, ensure_ascii=False))

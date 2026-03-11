#!/usr/bin/env python3
import tools.monkeypatch_model_calls
import sys
from pathlib import Path

SOUL = Path('SOUL.md')

def format_entry(text: str) -> str:
    # Basic normalisation: ensure starts with [禁止] or [推荐]
    t = text.strip()
    if not (t.startswith('[禁止]') or t.startswith('[推荐]')):
        # default to recommendation
        t = '[推荐] ' + t
    return '\n- ' + t + '\n'

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: learn "[推荐]/[禁止] ..."')
        sys.exit(2)
    entry = format_entry(sys.argv[1])
    with SOUL.open('a', encoding='utf-8') as f:
        f.write(entry)
    print('Appended to SOUL.md:', entry)

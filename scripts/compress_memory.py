#!/usr/bin/env python3
"""compress_memory.py

Enhancements:
- Archive memory/*.md files older than a configurable threshold (default 7 days) with a one-line summary.
- Produce prompt-ready summaries (short, <=200 tokens approximation) for MEMORY.md and archived files.
- Store prompt-ready summaries under .backups/prompt_summaries/ for use by callers before sending to LLM.

Notes:
- This implementation is local-only and does not call external LLMs.
- Token approximation: we treat 1 token ~= 4 characters for a conservative cap.
"""
import tools.monkeypatch_model_calls
from pathlib import Path
import datetime
import re
import json

ROOT = Path('.')
MEM_DIR = ROOT / 'memory'
MAIN = ROOT / 'MEMORY.md'
BACKUPS = ROOT / '.backups'
PROMPT_SUM_DIR = BACKUPS / 'prompt_summaries'
ARCHIVE_DAYS = 7
MAX_TOKENS = 200
CHARS_PER_TOKEN = 4  # conservative
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN

PROMPT_TEMPLATE = "Summary (short): {summary}\nSource: {source}\n"

def normalize_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def extract_key_sentence(text: str) -> str:
    # find sentences containing keywords, else fall back to first sentence
    kws = ['error','错误','失败','成功','备份','回滚','commit','push','token','CRLF','LF','just']
    sentences = re.split(r'(?<=[。.!?\n])\s*', text)
    sentences = [normalize_whitespace(s) for s in sentences if normalize_whitespace(s)]
    for s in sentences:
        lower = s.lower()
        for k in kws:
            if k in lower:
                return s
    # fallback: return first non-empty sentence or first 200 chars
    if sentences:
        return sentences[0][:MAX_CHARS]
    return normalize_whitespace(text)[:MAX_CHARS]


def make_prompt_ready(text: str, source: str) -> str:
    # produce a short summary <= MAX_CHARS characters
    s = extract_key_sentence(text)
    s = normalize_whitespace(s)
    if len(s) > MAX_CHARS:
        s = s[:MAX_CHARS-3] + '...'
    out = PROMPT_TEMPLATE.format(summary=s, source=source)
    # ensure final length within cap
    if len(out) > MAX_CHARS:
        out = out[:MAX_CHARS-3] + '...'
    return out


def archive_old_memories(days=ARCHIVE_DAYS):
    now = datetime.date.today()
    PROMPT_SUM_DIR.mkdir(parents=True, exist_ok=True)
    if not MEM_DIR.exists():
        return
    for p in MEM_DIR.glob('*.md'):
        try:
            parts = p.stem.split('-')
            if len(parts) == 3:
                y,m,d = map(int, parts)
                ddate = datetime.date(y,m,d)
                if (now - ddate).days > days:
                    text = p.read_text(encoding='utf-8')
                    summary = extract_key_sentence(text)
                    new = f"# {p.name} (archived)\n\n- summary: {summary}\n"
                    p.write_text(new, encoding='utf-8')
                    # also write a prompt-ready summary file
                    prompt = make_prompt_ready(text, p.name)
                    outp = PROMPT_SUM_DIR / f'{p.stem}-prompt.txt'
                    outp.write_text(prompt, encoding='utf-8')
        except Exception:
            continue


def compress_main_memory():
    PROMPT_SUM_DIR.mkdir(parents=True, exist_ok=True)
    if not MAIN.exists():
        return
    main_text = MAIN.read_text(encoding='utf-8')
    # keep only lines containing key words
    lines = [l.strip() for l in main_text.splitlines() if l.strip()]
    keep = [l for l in lines if any(k in l.lower() for k in ('坑','备份','回滚','commit','git','token','crlf','lf'))]
    if not keep:
        keep = lines[:10]
    new_main = '# 核心记忆 (compressed)\n\n' + '\n'.join('- '+l for l in keep) + '\n'
    MAIN.write_text(new_main, encoding='utf-8')
    # also create prompt-ready summary for MEMORY.md
    prompt = make_prompt_ready('\n'.join(keep), 'MEMORY.md')
    outp = PROMPT_SUM_DIR / 'MEMORY-prompt.txt'
    outp.write_text(prompt, encoding='utf-8')


if __name__ == '__main__':
    archive_old_memories()
    compress_main_memory()
    print('compress_memory: done')

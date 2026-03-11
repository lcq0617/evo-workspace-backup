#!/usr/bin/env python3
"""scripts/prompt_budget.py

Estimate prompt token usage and produce a prompt-ready fallback if over budget.
Usage:
  python scripts/prompt_budget.py --max-tokens 500 --file path/to/input.txt --summarize
  echo "very long text" | python scripts/prompt_budget.py --max-tokens 200

Behavior:
- Estimate tokens using a conservative chars->tokens heuristic (1 token ~= 4 chars).
- If estimated tokens <= max-tokens -> print JSON {allowed:true, tokens: N}
- If > max-tokens and --summarize provided: produce a short extractive summary (one sentence) that fits the budget and return it in the JSON {allowed:false, tokens:N, action:'summarize', summary: '...'}
- Always write a detailed check record to .backups/prompt_checks/<ts>.json for auditing.

This is purely local and does not call external APIs.
"""
import tools.monkeypatch_model_calls
from pathlib import Path
import argparse
import sys
import json
import datetime
import re

CHARS_PER_TOKEN = 4  # conservative
BACKUP_DIR = Path('.backups') / 'prompt_checks'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", ' ', s).strip()


def extract_key_sentence(text: str) -> str:
    # simple extractive: find sentence containing keywords or return first sentence
    kws = ['error','错误','失败','成功','备份','回滚','commit','push','token','crlf','lf','just']
    # split into sentences by punctuation and newlines
    sentences = re.split(r'(?<=[。.!?\n])\s*', text)
    sentences = [normalize_whitespace(s) for s in sentences if normalize_whitespace(s)]
    for s in sentences:
        lower = s.lower()
        for k in kws:
            if k in lower:
                return s
    return sentences[0] if sentences else ''


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def make_truncated(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars-3] + '...'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--max-tokens', type=int, default=300)
    p.add_argument('--file', type=str, help='Read input from file instead of stdin')
    p.add_argument('--summarize', action='store_true', help='Attempt extractive summary if over budget')
    args = p.parse_args()

    if args.file:
        txt = Path(args.file).read_text(encoding='utf-8')
    else:
        txt = sys.stdin.read()

    txt = normalize_whitespace(txt)
    est = estimate_tokens(txt)
    allowed = est <= args.max_tokens
    result = {'timestamp': datetime.datetime.now().isoformat(), 'tokens_estimate': est, 'max_tokens': args.max_tokens, 'allowed': allowed}

    if allowed:
        result['action'] = 'pass'
    else:
        if args.summarize:
            # produce extractive summary aimed to fit budget
            max_chars = args.max_tokens * CHARS_PER_TOKEN
            summary = extract_key_sentence(txt)
            if not summary:
                summary = txt[:max_chars]
            summary = make_truncated(summary, max_chars)
            result['action'] = 'summarize'
            result['summary'] = summary
            result['summary_tokens_est'] = estimate_tokens(summary)
        else:
            # provide a truncated version for quick use
            max_chars = args.max_tokens * CHARS_PER_TOKEN
            trunc = make_truncated(txt, max_chars)
            result['action'] = 'truncate'
            result['truncated'] = trunc
            result['truncated_tokens_est'] = estimate_tokens(trunc)

    # write audit record
    outp = BACKUP_DIR / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    outp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    # print JSON result to stdout
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()

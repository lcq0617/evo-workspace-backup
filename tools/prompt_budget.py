"""
prompt_budget.py - Prototype wrapper to enforce a token budget before sending prompts to a model.

Features (prototype v0.1):
- estimate_token_count(text): uses tiktoken if installed, else heuristic
- compress_context(text, max_tokens): extractive compressor that keeps headings and first sentences of paragraphs, writes full content to memory/ as a reference file and replaces with a <REF:...> placeholder
- CLI: accepts --input-file or reads stdin, --max-tokens, --out-file

Usage examples:
  python tools/prompt_budget.py --input-file prompts/long_prompt.txt --max-tokens 20000 --out-file prompts/compressed.json

Notes:
- This is a local helper. It does NOT call external APIs.
- For production, connect the compressor to a summarization model or embeddings-based selector.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from datetime import datetime

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MEMORY_DIR = os.path.join(WORKSPACE, 'memory')
os.makedirs(MEMORY_DIR, exist_ok=True)


def estimate_token_count(text: str) -> int:
    """Estimate tokens. Try importing tiktoken; fallback to heuristic (words / 0.75).
    Lower bound: 1 token per 4 chars (very rough)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text))
    except Exception:
        # fallback heuristic: tokens ~= words / 0.75
        words = len(text.split())
        return int(words / 0.75) if words > 0 else 0


def _first_sentence_of_paragraph(p: str) -> str:
    # split by sentence enders. Keep first sensible chunk
    m = re.split(r"(?<=[\.\?!。！？])\s+", p.strip())
    return m[0].strip() if m and m[0] else p.strip()


def compress_context(text: str, max_tokens: int, tag_hint: str = 'auto') -> dict:
    """Compress text extractively to meet max_tokens.

    Strategy:
    1) If within budget, return original
    2) Split into paragraphs. Keep headings (lines that look like headings) and first sentence of each paragraph.
    3) If still over budget, keep only first N paragraphs.
    4) Save full original into memory/<sha>-<ts>.txt and replace with placeholder <REF:sha>

    Returns dict with keys: compressed_text, original_ref (path or None), original_tokens, compressed_tokens
    """
    orig_tokens = estimate_token_count(text)
    if orig_tokens <= max_tokens:
        return {
            'compressed_text': text,
            'original_ref': None,
            'original_tokens': orig_tokens,
            'compressed_tokens': orig_tokens,
        }

    # create reference file
    sha = hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    fname = f'prompt_ref_{sha}_{ts}.txt'
    fpath = os.path.join(MEMORY_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(text)

    # split into paragraphs
    paragraphs = [p for p in re.split(r"\n{2,}", text) if p.strip()]

    # pick headings + first sentences
    picks = []
    for p in paragraphs:
        # heading detection: short line, ends with ':' or all-caps or starts with '#'
        lines = p.strip().splitlines()
        first_line = lines[0].strip()
        if first_line.startswith('#') or len(first_line) < 120 and first_line.isupper() or first_line.endswith(':'):
            picks.append(first_line)
        else:
            picks.append(_first_sentence_of_paragraph(p))

    # join and measure
    compressed = '\n\n'.join(picks)
    comp_tokens = estimate_token_count(compressed)

    if comp_tokens <= max_tokens:
        placeholder = f"<REF:{fname}>\n---\n{compressed}"
        return {
            'compressed_text': placeholder,
            'original_ref': fpath,
            'original_tokens': orig_tokens,
            'compressed_tokens': comp_tokens,
        }

    # still too large: keep only first N paragraphs greedily
    kept = []
    for p in picks:
        kept.append(p)
        compressed = '\n\n'.join(kept)
        if estimate_token_count(compressed) > max_tokens:
            # remove last and stop
            kept.pop()
            break

    if not kept:
        # very small budget: keep a short prefix
        max_chars = int(max_tokens * 4)  # rough heuristic
        compressed = text[:max_chars].rsplit('\n', 1)[0]
    else:
        compressed = '\n\n'.join(kept)

    comp_tokens = estimate_token_count(compressed)
    placeholder = f"<REF:{fname}>\n---\n{compressed}"
    return {
        'compressed_text': placeholder,
        'original_ref': fpath,
        'original_tokens': orig_tokens,
        'compressed_tokens': comp_tokens,
    }


def cli():
    p = argparse.ArgumentParser(description='Prompt budget prototype - compress prompts to fit token budget')
    p.add_argument('--input-file', '-i', help='Input file path (if omitted read stdin)')
    p.add_argument('--max-tokens', '-m', type=int, default=20000, help='Token budget (default 20000)')
    p.add_argument('--out-file', '-o', help='Write JSON output to path (else stdout)')
    args = p.parse_args()

    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        import sys
        text = sys.stdin.read()

    res = compress_context(text, args.max_tokens)
    output = {
        'max_tokens': args.max_tokens,
        'original_tokens': res['original_tokens'],
        'compressed_tokens': res['compressed_tokens'],
        'original_ref': res['original_ref'],
        'compressed_text': res['compressed_text'],
    }

    out_json = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out_file:
        with open(args.out_file, 'w', encoding='utf-8') as f:
            f.write(out_json)
        print(f'WROTE {args.out_file}')
    else:
        print(out_json)


if __name__ == '__main__':
    cli()

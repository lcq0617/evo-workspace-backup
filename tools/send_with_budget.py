"""
send_with_budget.py - small helper to wrap model/send calls with prompt budget enforcement.

Usage:
  from tools.send_with_budget import send_with_budget

  def raw_send(prompt_text):
      # call your model client here and return result
      return my_model_client.send(prompt_text)

  result = send_with_budget(raw_send, prompt_text, max_tokens=20000)

The function compresses the prompt using tools/prompt_budget.compress_context, writes the full original to memory/ (if compressed), and passes the compressed placeholder to the provided send_fn.
It returns a dict { 'result': <send_fn return>, 'meta': { ... } }

This is intentionally runtime-agnostic: you provide the actual sender callable so it works in Python services or quick patches.
"""
from __future__ import annotations
import typing as t
import os
import json
from .prompt_budget import compress_context, estimate_token_count

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MEMORY_DIR = os.path.join(WORKSPACE, 'memory')
os.makedirs(MEMORY_DIR, exist_ok=True)


def send_with_budget(send_fn: t.Callable[[str], t.Any], prompt_text: str, *, max_tokens: int = 20000, tag: str | None = None) -> dict:
    """Compress prompt_text to max_tokens, call send_fn with the compressed text, return result and metadata.

    send_fn should be a callable that accepts a single string (the prompt to send) and returns whatever the model/client returns.
    """
    # do compression
    res = compress_context(prompt_text, max_tokens, tag_hint=tag or 'send_with_budget')
    compressed = res['compressed_text']

    # call send_fn with compressed prompt
    result = send_fn(compressed)

    meta = {
        'max_tokens': max_tokens,
        'original_tokens': res.get('original_tokens'),
        'compressed_tokens': res.get('compressed_tokens'),
        'original_ref': res.get('original_ref'),
    }
    return {'result': result, 'meta': meta}


# convenience CLI
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--input-file', '-i')
    p.add_argument('--max-tokens', '-m', type=int, default=20000)
    args = p.parse_args()
    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        import sys
        text = sys.stdin.read()

    def _echo(s: str):
        print('--- SENDING (compressed prompt) ---')
        print(s)
        return 'ECHOED'

    out = send_with_budget(_echo, text, max_tokens=args.max_tokens)
    print('\nMETA:\n', json.dumps(out['meta'], ensure_ascii=False, indent=2))

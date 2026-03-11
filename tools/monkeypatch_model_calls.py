"""
monkeypatch_model_calls.py

Non-destructive runtime monkeypatch to enforce prompt budget on common Python clients.
Behavior:
- On import, attempts to patch `openai.ChatCompletion.create`, `openai.ChatCompletion.acreate`, `openai.Completion.create` if openai is importable.
- For patched calls, it estimates tokens of prompt/messages, uses tools.prompt_budget.compress_context to compress when over budget (default 20000 or env PROMPT_BUDGET), replaces the outgoing prompt/messages with the compressed placeholder, and logs metadata to memory/monkeypatch_log.jsonl.
- If openai isn't present, the module is a no-op.

Notes:
- This is conservative but will change outgoing messages when compression happens (it replaces messages/prompt with a single system message containing the compressed placeholder and snippet). That is the agreed behavior to respect token budgets.
- All exceptions are re-raised; failures are logged.
"""
from __future__ import annotations
import os
import json
import functools
import traceback
from datetime import datetime

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MEMORY_DIR = os.path.join(WORKSPACE, 'memory')
os.makedirs(MEMORY_DIR, exist_ok=True)
LOG_PATH = os.path.join(MEMORY_DIR, 'monkeypatch_log.jsonl')

# budget default; can be overridden with PROMPT_BUDGET env var
try:
    DEFAULT_BUDGET = int(os.environ.get('PROMPT_BUDGET', '20000'))
except Exception:
    DEFAULT_BUDGET = 20000

# lightweight token estimation reuse
try:
    from .prompt_budget import estimate_token_count, compress_context
except Exception:
    # try direct import path if run as script
    try:
        from tools.prompt_budget import estimate_token_count, compress_context
    except Exception:
        def estimate_token_count(text: str) -> int:
            return max(1, len(text.split()))
        def compress_context(text: str, max_tokens: int, tag_hint: str = 'auto'):
            return {'compressed_text': text, 'original_ref': None, 'original_tokens': estimate_token_count(text), 'compressed_tokens': estimate_token_count(text)}


def _log(obj: dict):
    obj['ts'] = datetime.utcnow().isoformat() + 'Z'
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _gather_messages(kwargs: dict) -> str | None:
    # try to extract prompt text from common args
    if 'messages' in kwargs and isinstance(kwargs['messages'], (list, tuple)):
        parts = []
        for m in kwargs['messages']:
            try:
                role = m.get('role','')
                cont = m.get('content','')
                parts.append(f"[{role}] {cont}")
            except Exception:
                parts.append(str(m))
        return '\n\n'.join(parts)
    if 'prompt' in kwargs and isinstance(kwargs['prompt'], (str,)):
        return kwargs['prompt']
    return None


def _apply_compression_to_kwargs(kwargs: dict, compressed_text: str):
    # replace messages or prompt with compressed placeholder in a conservative way
    if 'messages' in kwargs:
        kwargs['messages'] = [{'role':'system','content':compressed_text}]
    elif 'prompt' in kwargs:
        kwargs['prompt'] = compressed_text
    else:
        # nothing to replace; inject a system message param if possible
        kwargs['prompt'] = compressed_text
    return kwargs


def _make_wrapper(orig_fn, *, max_tokens=DEFAULT_BUDGET, name=None):
    @functools.wraps(orig_fn)
    def wrapper(*args, **kwargs):
        try:
            prompt_text = _gather_messages(kwargs) or (args[0] if args else None)
            if isinstance(prompt_text, str):
                orig_tokens = estimate_token_count(prompt_text)
                if orig_tokens > max_tokens:
                    comp = compress_context(prompt_text, max_tokens, tag_hint='monkeypatch')
                    compressed_text = comp.get('compressed_text')
                    _apply_compression_to_kwargs(kwargs, compressed_text)
                    meta = {
                        'action': 'compressed',
                        'name': name or getattr(orig_fn, '__name__', 'unknown'),
                        'original_tokens': comp.get('original_tokens'),
                        'compressed_tokens': comp.get('compressed_tokens'),
                        'original_ref': comp.get('original_ref'),
                    }
                    _log({'meta': meta})
            result = orig_fn(*args, **kwargs)
            return result
        except Exception as e:
            # log exception and re-raise
            _log({'action': 'error', 'name': name or getattr(orig_fn, '__name__','unknown'), 'error': str(e), 'trace': traceback.format_exc()})
            raise
    # async wrapper
    async def awrapper(*args, **kwargs):
        try:
            prompt_text = _gather_messages(kwargs) or (args[0] if args else None)
            if isinstance(prompt_text, str):
                orig_tokens = estimate_token_count(prompt_text)
                if orig_tokens > max_tokens:
                    comp = compress_context(prompt_text, max_tokens, tag_hint='monkeypatch')
                    compressed_text = comp.get('compressed_text')
                    _apply_compression_to_kwargs(kwargs, compressed_text)
                    meta = {
                        'action': 'compressed',
                        'name': name or getattr(orig_fn, '__name__', 'unknown'),
                        'original_tokens': comp.get('original_tokens'),
                        'compressed_tokens': comp.get('compressed_tokens'),
                        'original_ref': comp.get('original_ref'),
                    }
                    _log({'meta': meta})
            result = await orig_fn(*args, **kwargs)
            return result
        except Exception as e:
            _log({'action': 'error', 'name': name or getattr(orig_fn, '__name__','unknown'), 'error': str(e), 'trace': traceback.format_exc()})
            raise

    # choose wrapper type based on whether orig_fn is coroutinefunction
    try:
        import inspect
        if inspect.iscoroutinefunction(orig_fn):
            return awrapper
    except Exception:
        pass
    return wrapper


# Attempt to patch openai
try:
    import openai
    try:
        if hasattr(openai, 'ChatCompletion'):
            if hasattr(openai.ChatCompletion, 'create'):
                openai.ChatCompletion.create = _make_wrapper(openai.ChatCompletion.create, name='openai.ChatCompletion.create')
            if hasattr(openai.ChatCompletion, 'acreate'):
                openai.ChatCompletion.acreate = _make_wrapper(openai.ChatCompletion.acreate, name='openai.ChatCompletion.acreate')
        if hasattr(openai, 'Completion') and hasattr(openai.Completion, 'create'):
            openai.Completion.create = _make_wrapper(openai.Completion.create, name='openai.Completion.create')
        _log({'action':'patched','target':'openai'})
    except Exception as e:
        _log({'action':'patch_failed','target':'openai','error':str(e),'trace':traceback.format_exc()})
except Exception:
    # openai not installed; no-op
    _log({'action':'noop','reason':'openai_not_importable'})

# end of module

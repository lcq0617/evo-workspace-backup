import tools.monkeypatch_model_calls
# llm_guard.py
# Runtime guards that monkeypatch common LLM client entrypoints to enforce prompt budget
from __future__ import annotations
import logging
from pathlib import Path

log = logging.getLogger('llm_guard')
BACKUP_DIR = Path('.backups') / 'prompt_checks'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

try:
    from scripts.prompt_utils import prepare_prompt
except Exception:
    # fallback simple implementation
    def prepare_prompt(text, max_tokens=300, summarize=True):
        return {'allowed': True, 'prompt': text}


def _audit_write(data, tag='llm_guard'):
    try:
        import json, datetime
        outp = BACKUP_DIR / (f'{tag}_' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        outp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _wrap_openai():
    try:
        import openai
    except Exception:
        return False
    # wrap ChatCompletion.create and Completion.create if exist
    if hasattr(openai, 'ChatCompletion'):
        orig = openai.ChatCompletion.create
        def wrapped_create(*args, **kwargs):
            try:
                # messages may be in kwargs or in args
                msgs = kwargs.get('messages')
                if msgs is None and len(args) >= 1:
                    # might be positional
                    pass
                if msgs and isinstance(msgs, list):
                    # extract content concatenation
                    full = '\n'.join(m.get('content','') for m in msgs if isinstance(m, dict))
                    res = prepare_prompt(full)
                    if not res.get('allowed'):
                        # replace messages with single summary message
                        summary = res.get('prompt')
                        kwargs['messages'] = [{'role':'system','content': summary}]
                        _audit_write({'action':'openai_summarize','summary_len': len(summary)})
                return orig(*args, **kwargs)
            except Exception as e:
                log.exception('llm_guard openai wrapper failed')
                return orig(*args, **kwargs)
        openai.ChatCompletion.create = wrapped_create
    if hasattr(openai, 'Completion'):
        orig = openai.Completion.create
        def wrapped_create2(*args, **kwargs):
            try:
                prompt = kwargs.get('prompt')
                if prompt:
                    res = prepare_prompt(prompt)
                    if not res.get('allowed'):
                        kwargs['prompt'] = res.get('prompt')
                        _audit_write({'action':'openai_completion_summarize'})
                return orig(*args, **kwargs)
            except Exception:
                return orig(*args, **kwargs)
        openai.Completion.create = wrapped_create2
    return True


def _wrap_requests():
    try:
        import requests
    except Exception:
        return False
    try:
        session_request = requests.sessions.Session.request
        def wrapped_request(self, method, url, *args, **kwargs):
            try:
                jsonp = kwargs.get('json')
                if isinstance(jsonp, dict):
                    # find keys that look like prompts
                    for k in ('prompt','messages','input','inputs'):
                        if k in jsonp:
                            val = jsonp[k]
                            if isinstance(val, list):
                                full = '\n'.join(v.get('content', '') if isinstance(v, dict) else str(v) for v in val)
                                res = prepare_prompt(full)
                                if not res.get('allowed'):
                                    jsonp[k] = [{'role':'system','content': res.get('prompt')}]
                                    kwargs['json'] = jsonp
                                    _audit_write({'action':'requests_summarize','url':url})
                            elif isinstance(val, str):
                                res = prepare_prompt(val)
                                if not res.get('allowed'):
                                    jsonp[k] = res.get('prompt')
                                    kwargs['json'] = jsonp
                                    _audit_write({'action':'requests_summarize','url':url})
                return session_request(self, method, url, *args, **kwargs)
            except Exception:
                return session_request(self, method, url, *args, **kwargs)
        requests.sessions.Session.request = wrapped_request
        return True
    except Exception:
        return False


def install_guards():
    """Call at program startup to install guards when possible."""
    _wrap_openai()
    _wrap_requests()
    log.info('llm_guard installed')

if __name__ == '__main__':
    install_guards()
    print('llm_guard active')

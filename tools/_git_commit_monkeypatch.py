import subprocess, sys
files = ['tools/monkeypatch_model_calls.py']
try:
    subprocess.run(['git','add'] + files, check=True)
    subprocess.run(['git','commit','-m','feat: runtime monkeypatch to enforce prompt budget on openai clients; log compression events to memory/monkeypatch_log.jsonl'], check=True)
    print('COMMIT_OK')
except subprocess.CalledProcessError as e:
    print('COMMIT_FAILED')
    print('returncode:', e.returncode)
    if e.output:
        print(e.output)
    sys.exit(1)

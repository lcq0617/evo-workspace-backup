set shell := {bash}

# Backup/rollback helpers
backup:
	python scripts/safe_iter.py

rollback commit:
	python scripts/rollback.py {{commit}}

history:
	ls -1 .backups | tail -n 50

# Learning helper: append a lesson to SOUL.md
learn args:
	python scripts/learn.py "{{args}}"

# Daily review
review:
	python scripts/daily_review.py

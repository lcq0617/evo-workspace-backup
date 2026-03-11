# Justfile - workspace helper recipes

# Backup: create a commit with given message and record commit hash
backup msg:
    @bash -lc 'git add -A && git commit -m "${msg}" || echo "no changes to commit"'
    @bash -lc 'git rev-parse HEAD > .backups/last_commit.txt || true'
    @bash -lc 'mkdir -p .backups && echo "{\"ts\": \"$(date +%Y%m%d-%H%M%S)\", \"commit\": \"$(cat .backups/last_commit.txt 2>/dev/null)\", \"msg\": "${msg}"}" > .backups/$(date +%Y%m%d-%H%M%S).json || true'

# Rollback: revert to given commit hash or the last backup
rollback commit:
    @bash -lc 'if [ -n "${commit}" ]; then echo "Rolling back to ${commit}" && git reset --hard "${commit}" && git clean -fd; else LAST=$(ls -1 .backups | tail -n1) && if [ -n "$LAST" ]; then CH=$(jq -r .commit .backups/$LAST) && echo "Rolling back to $CH" && git reset --hard $CH && git clean -fd; else echo "No backups found."; fi; fi'

# History: show recent backups and last 5 commits
history:
    @bash -lc 'echo "Recent backups:" && ls -1 .backups | tail -n 5 || true'
    @bash -lc 'echo "Recent git commits:" && git log --oneline -n 5 || true'

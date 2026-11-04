#!/bin/bash
# Waits for Edison's batch in WSL to finish, then runs tribunals on the most contested issues.
# Run from C:\dev\switch in Git Bash:  bash scripts/finish_pipeline.sh > cache/pipeline.log 2>&1
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf8
SSH="/c/Windows/System32/OpenSSH/ssh.exe -o BatchMode=yes -o ConnectTimeout=30 wsl-switch"
until $SSH 'grep -q "== batch3 done" ~/vegapunk-work/batch3.log' 2>/dev/null; do sleep 120; done
echo "== edison finished $(date)"
uv run -q python -m vegapunk.ingest          # pick up PRs opened since the last run
uv run -q python -m vegapunk.council --top 8 --timeout 2700
echo "== council finished $(date)"

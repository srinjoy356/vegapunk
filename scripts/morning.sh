#!/bin/bash
# Prove the PRs opened since the last Edison pass, refresh outputs, push.
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf8
cd /c/dev/switch
W() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u srinjoy -- bash -lc "$1" 2>/dev/null; }
until W 'grep -q "batch4 done" ~/vegapunk-work/batch6.log'; do sleep 120; done
uv run -q python -m vegapunk.report; uv run -q python -m vegapunk.results
git add docs/results.md scripts && git commit -qm "Edison pass over newly opened PRs; refresh results" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q; echo "== morning done $(date)"

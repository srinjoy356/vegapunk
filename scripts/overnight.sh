#!/bin/bash
# Overnight: wait for Edison, retry weak tribunals, rank more contested issues, regenerate outputs, push.
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf8
cd /c/dev/switch
W() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u srinjoy -- bash -lc "$1" 2>/dev/null; }
until W 'grep -q "batch4 done" ~/vegapunk-work/batch5.log'; do sleep 120; done
echo "== edison done $(date)"
uv run -q python -m vegapunk.ingest
for round in 1 2 3; do
  W 'pkill -f agy_acp_server; true'
  echo "== council round $round $(date)"
  uv run -q python -m vegapunk.council --issues 828 805 --timeout 2400
  W 'pkill -f agy_acp_server; true'
  uv run -q python -m vegapunk.council --top 14 --timeout 2400
done
uv run -q python -m vegapunk.report
uv run -q python -m vegapunk.results
git add docs/results.md scripts && git commit -qm "Overnight council run: refresh results" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q
echo "== overnight finished $(date)"

#!/bin/bash
export PATH=$HOME/.local/bin:$PATH UV_PROJECT_ENVIRONMENT=$HOME/vegapunk-work/venv
cd /mnt/c/dev/switch
E="uv run -q python -m vegapunk.edison"
echo "== batch4 start $(date)"
$E --all --atlas --jobs 1
$E --all --matrix --jobs 1 --no-fetch
echo "== batch4 done $(date)"

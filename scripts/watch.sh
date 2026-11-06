#!/bin/bash
# Keeps the Punk Records watch loop (human picks, verdict collection) alive across outages.
cd /c/dev/switch; export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf8
while true; do uv run -q python -m vegapunk.tribunal watch >> cache/tribunal/watch.log 2>&1; sleep 15; done

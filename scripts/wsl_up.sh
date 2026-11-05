#!/bin/bash
# Bring the Vegapunk stack back after a WSL restart (run inside Ubuntu as srinjoy).
docker start switchdash-remote-postgres-1 switchdash-remote-mattermost-1 >/dev/null; sleep 15
docker start switchdash-remote-switch-1 switchdash-remote-gateway-1 >/dev/null; sleep 20
cd ~/.local/state/switch/sdk-host
D=~/.local/state/switch/agent-controller/console-a7f0fd1a-0e53-4cdd-aae5-e3eeb1e48d9d
nohup setsid node $PWD/agent-controller-*.mjs run --data-dir $D --shared-host-bundle $(ls $PWD/shared-host-*.mjs) --updated-by-console > ~/controller-manual.log 2>&1 < /dev/null &
sleep 5
nohup setsid bash ~/vegapunk-work/batch4.sh > ~/vegapunk-work/batch4.log 2>&1 < /dev/null &
sleep 30; docker ps --format '{{.Names}} {{.Status}}'; tail -n 2 ~/controller-manual.log | cut -c1-160

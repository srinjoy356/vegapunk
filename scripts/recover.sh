#!/bin/bash
# Bring Ubuntu WSL, Egghead containers and the agent controller back after a hang.
W() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u srinjoy -- bash -lc "$1" 2>/dev/null; }
wsl.exe --shutdown; sleep 8
powershell -NoProfile -c "Start-Process -WindowStyle Hidden wsl -ArgumentList '-d','Ubuntu','-u','srinjoy','--','sleep','infinity'"
sleep 10
W 'grep -v batch4 /mnt/c/dev/switch/scripts/wsl_up.sh | tr -d "\r" > ~/wsl_up2.sh; bash ~/wsl_up2.sh > ~/wsl_up.out 2>&1; nohup setsid bash -c "while true; do bash ~/reap.sh; sleep 600; done" >/dev/null 2>&1 </dev/null &'

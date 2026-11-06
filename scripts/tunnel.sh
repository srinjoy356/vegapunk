#!/bin/bash
# Keeps the Windows -> Ubuntu SSH port bridge to the Switch server alive (Console's own bridge drops).
while true; do
  /c/Windows/System32/OpenSSH/ssh.exe -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 \
    -L 127.0.0.1:10958:127.0.0.1:10958 -L 127.0.0.1:10957:127.0.0.1:10957 wsl-switch
  sleep 5
done

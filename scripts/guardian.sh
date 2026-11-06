#!/bin/bash
# Every 3 min: if the Switch API is unreachable twice in a row, recover WSL.
bad=0
while true; do
  c=$(curl -s -o /dev/null -m 8 -w "%{http_code}" http://127.0.0.1:10958/)
  if [ "$c" = 200 ]; then bad=0; else bad=$((bad+1)); fi
  if [ $bad -ge 2 ]; then echo "$(date) recovering"; bash /c/dev/switch/scripts/recover.sh; bad=0; fi
  sleep 180
done

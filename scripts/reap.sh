#!/bin/bash
# kill agent sessions idle for over an hour (keeps live tribunal sessions)
ps -eo pid,etimes,args | awk '/claude --output-format|agy_acp_server/ && !/awk/ && $2>1800 {print $1}' | xargs -r kill

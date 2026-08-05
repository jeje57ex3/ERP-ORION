#!/usr/bin/env bash
# Attend qu'un port TCP local soit ouvert. Usage : wait_for_port.sh HOST PORT [TIMEOUT_SEC]
set -euo pipefail

HOST="${1:?usage: wait_for_port.sh HOST PORT [TIMEOUT_SEC]}"
PORT="${2:?usage: wait_for_port.sh HOST PORT [TIMEOUT_SEC]}"
TIMEOUT="${3:-60}"

ELAPSED=0
while ! (exec 3<>"/dev/tcp/$HOST/$PORT") 2>/dev/null; do
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "wait_for_port: timeout après ${TIMEOUT}s sur ${HOST}:${PORT}" >&2
    exit 1
  fi
  sleep 1
  ELAPSED=$((ELAPSED + 1))
done
exec 3<&- 2>/dev/null || true
exit 0

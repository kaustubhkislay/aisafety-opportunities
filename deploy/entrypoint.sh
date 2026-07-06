#!/bin/bash
# Run all four long-lived processes; if any one dies, exit so the Fly machine
# restarts (crash-safe by design: ingest is idempotent, the worker leaves
# unprocessed rows, the bot re-backfills from its cursors).
set -m

python -m bot.client &
python -m backend.worker &
supercronic /app/deploy/crontab &
uvicorn backend.app:app --host 0.0.0.0 --port 8080 &

wait -n
echo "a process exited; restarting machine" >&2
exit 1

# Single-machine deployment: the ingest API, extraction worker, Discord bot,
# and the cron jobs all share one filesystem because they share the SQLite
# stores (raw.db holds both the bot's cursors and the worker's queue).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

# supercronic: container-friendly cron (keeps env vars, logs to stdout)
ADD https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

WORKDIR /app

# Install locked dependencies system-wide (the project itself is not a package).
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project > requirements.txt \
    && uv pip install --system -r requirements.txt

COPY backend ./backend
COPY bot ./bot
COPY slackbot ./slackbot
COPY deploy/crontab deploy/entrypoint.sh ./deploy/
RUN chmod +x deploy/entrypoint.sh

CMD ["./deploy/entrypoint.sh"]

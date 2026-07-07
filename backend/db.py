"""Shared SQLite connection factory.

Four long-lived processes (API, worker, Discord bot, cron jobs) share the
SQLite files on the Fly volume. sqlite's defaults — rollback journal and a
zero busy timeout — turn any writer collision into an immediate
'database is locked' error; WAL lets readers and one writer coexist and the
busy timeout makes colliding writers wait instead of failing.
"""

import sqlite3


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

"""Shared SQLite connection settings: WAL + busy timeout.

Four processes and two cron jobs write these files concurrently; sqlite's
defaults (rollback journal, zero busy timeout) turn collisions into instant
'database is locked' errors.
"""

from backend.db import connect


def test_connections_use_wal_and_busy_timeout(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    conn.execute("CREATE TABLE t (x)")  # usable connection
    conn.close()


def test_all_stores_inherit_wal(tmp_path):
    from backend.store import RawStore
    from backend.subscribers import SubscriberStore
    from slackbot.tokens import TokenStore

    for store in (
        RawStore(str(tmp_path / "raw.db")),
        SubscriberStore(str(tmp_path / "subs.db")),
        TokenStore(str(tmp_path / "tok.db")),
    ):
        store.init_db()
        conn = store._connect()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        conn.close()

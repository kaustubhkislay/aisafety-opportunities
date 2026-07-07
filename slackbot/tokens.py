"""Per-workspace Slack install store.

Operational data (like SubscriberStore), kept in SQLite on the /data volume.
Bot tokens live only here — never in env or logs. The row is deleted on
uninstall/revocation, which is the Slack analogue of the Discord kick-purge.
"""

import sqlite3

from backend.db import connect


class TokenStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS installs (
                    team_id TEXT PRIMARY KEY,
                    team_name TEXT NOT NULL DEFAULT '',
                    bot_token TEXT NOT NULL,
                    bot_user_id TEXT NOT NULL DEFAULT '',
                    installed_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def save(self, team_id: str, team_name: str, bot_token: str, bot_user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO installs (team_id, team_name, bot_token, bot_user_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    team_name = excluded.team_name,
                    bot_token = excluded.bot_token,
                    bot_user_id = excluded.bot_user_id
                """,
                (team_id, team_name, bot_token, bot_user_id),
            )

    def get(self, team_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT team_id, team_name, bot_token, bot_user_id FROM installs "
                "WHERE team_id = ?",
                (team_id,),
            ).fetchone()
            return dict(row) if row else None

    def delete(self, team_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM installs WHERE team_id = ?", (team_id,))
            return cur.rowcount == 1

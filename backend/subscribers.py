"""Email-digest subscriber store (Slice 6 / T4.1).

Operational data (not the canonical opportunity store), kept in SQLite alongside
the raw message store. Stores subscriber emails with an active flag so unsubscribe
is a soft toggle and re-subscribe just reactivates.
"""

import sqlite3


class SubscriberStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscribers (
                    email TEXT PRIMARY KEY,
                    active INTEGER NOT NULL DEFAULT 1,
                    subscribed_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    @staticmethod
    def _normalize(email: str) -> str:
        return email.strip().lower()

    def add(self, email: str) -> bool:
        """Subscribe (or reactivate). Returns True if this changed state."""
        email = self._normalize(email)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT active FROM subscribers WHERE email = ?", (email,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO subscribers (email, active) VALUES (?, 1)", (email,)
                )
                return True
            if row["active"] == 0:
                conn.execute(
                    "UPDATE subscribers SET active = 1 WHERE email = ?", (email,)
                )
                return True
            return False  # already active

    def remove(self, email: str) -> bool:
        """Unsubscribe. Returns True if an active subscriber was deactivated."""
        email = self._normalize(email)
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE subscribers SET active = 0 WHERE email = ? AND active = 1",
                (email,),
            )
            return cur.rowcount == 1

    def active_emails(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT email FROM subscribers WHERE active = 1 ORDER BY email"
            ).fetchall()
            return [row["email"] for row in rows]

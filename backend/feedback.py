"""Site feedback store: a small SQLite table behind the public /feedback
endpoint (the website's feedback form posts here via its /api/feedback proxy).
"""

import sqlite3


class FeedbackStore:
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
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def add(self, message: str, email: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO feedback (message, email) VALUES (?, ?)",
                (message, email),
            )

    def all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM feedback ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]

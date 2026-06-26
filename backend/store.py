import sqlite3

_MESSAGE_COLUMNS = [
    "server_id",
    "channel_id",
    "message_id",
    "author_id",
    "content",
    "created_at",
]


class RawStore:
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
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    author_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def insert_message(self, msg: dict) -> bool:
        values = [msg[col] for col in _MESSAGE_COLUMNS]
        placeholders = ", ".join("?" for _ in _MESSAGE_COLUMNS)
        columns = ", ".join(_MESSAGE_COLUMNS)
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT OR IGNORE INTO messages ({columns}) VALUES ({placeholders})",
                values,
            )
            return cur.rowcount == 1

    def get_messages(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id ASC"
            ).fetchall()
            return [dict(row) for row in rows]

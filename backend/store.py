import sqlite3

_MESSAGE_COLUMNS = [
    "server_id",
    "server_name",
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cursors (
                    channel_id TEXT PRIMARY KEY,
                    last_message_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            existing = [
                row["name"]
                for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            ]
            if "processed_at" not in existing:
                conn.execute("ALTER TABLE messages ADD COLUMN processed_at TEXT")
            if "server_name" not in existing:
                conn.execute(
                    "ALTER TABLE messages ADD COLUMN server_name TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_processed_at "
                "ON messages(processed_at)"
            )

    def insert_message(self, msg: dict) -> bool:
        values = [msg.get(col, "") for col in _MESSAGE_COLUMNS]
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

    def get_messages_by_server(self, server_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE server_id = ? ORDER BY id ASC",
                (server_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_server(self, server_id: str) -> int:
        """Delete all raw rows for a server (uninstall purge). Returns count."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages WHERE server_id = ?", (server_id,))
            return cur.rowcount

    def get_cursor(self, channel_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_message_id FROM cursors WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            return row["last_message_id"] if row else None

    def set_cursor(self, channel_id: str, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cursors (channel_id, last_message_id)
                VALUES (?, ?)
                ON CONFLICT(channel_id)
                DO UPDATE SET last_message_id = excluded.last_message_id,
                              updated_at = datetime('now')
                WHERE CAST(excluded.last_message_id AS INTEGER)
                      > CAST(cursors.last_message_id AS INTEGER)
                """,
                (channel_id, message_id),
            )

    def claim_unprocessed(self, limit: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE processed_at IS NULL "
                "ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def is_processed(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE message_id = ? "
                "AND processed_at IS NOT NULL",
                (message_id,),
            ).fetchone()
            return row is not None

    def mark_processed(self, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET processed_at = datetime('now') "
                "WHERE message_id = ?",
                (message_id,),
            )

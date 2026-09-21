"""SQLite-backed message log for the text-chat tab. Shares broker/tasks.db with
the Hermes task rows (see broker/store.py, whose sqlite3 + threading.Lock
pattern this mirrors exactly) rather than a second DB file -- same process,
separate table, independent connection (SQLite allows multiple connections to
one file).
"""

import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  role       TEXT NOT NULL,
  content    TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


class ChatStore:
    def __init__(self, db_path):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def append(self, role, content):
        with self.lock:
            self.conn.execute(
                "INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, time.time()),
            )
            self.conn.commit()

    def get_all(self):
        with self.lock:
            self.conn.row_factory = sqlite3.Row
            rows = self.conn.execute("SELECT * FROM chat_messages ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]

    def clear(self):
        with self.lock:
            self.conn.execute("DELETE FROM chat_messages")
            self.conn.commit()

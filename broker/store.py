import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id            TEXT PRIMARY KEY,
  objective     TEXT NOT NULL,
  task_type     TEXT NOT NULL,
  risk          TEXT NOT NULL,
  status        TEXT NOT NULL,
  workdir       TEXT NOT NULL,
  created_at    REAL NOT NULL,
  started_at    REAL,
  finished_at   REAL,
  summary       TEXT,
  raw_output    TEXT,
  error         TEXT,
  cost_usd      REAL,
  delivered     INTEGER DEFAULT 0
);
"""

class TaskStore:
    def __init__(self, db_path):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def insert(self, task_id, objective, task_type, risk, workdir):
        with self.lock:
            self.conn.execute("""
                INSERT INTO tasks (id, objective, task_type, risk, status, workdir, created_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
            """,
            (task_id, objective, task_type, risk, workdir, time.time()))
            self.conn.commit()

    def update_result(self, task_id, status, summary=None, raw_output=None, error=None, cost_usd=None):
        with self.lock:
            self.conn.execute("""
                UPDATE tasks SET status=?, summary=?, raw_output=?, error=?, cost_usd=?, finished_at=?
                WHERE id=?
            """,
            (status, summary, raw_output, error, cost_usd, time.time(), task_id))
            self.conn.commit()

    def get(self, task_id):
        with self.lock:
            self.conn.row_factory = sqlite3.Row
            return self.conn.execute("""
                SELECT * FROM tasks WHERE id=?
            """, 
            (task_id,)).fetchone()

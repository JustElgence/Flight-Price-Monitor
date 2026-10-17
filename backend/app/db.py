"""SQLite access layer (WAL, plain SQL)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_task(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dep TEXT NOT NULL,
  arr TEXT NOT NULL,
  date TEXT NOT NULL,
  threshold REAL,
  interval_min INTEGER DEFAULT 480,
  enabled INTEGER DEFAULT 1,
  last_crawled_at TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS price_record(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  captured_at TEXT NOT NULL,
  target_date TEXT NOT NULL,
  min_price REAL,
  flight_no TEXT
);
CREATE INDEX IF NOT EXISTS idx_pr_task ON price_record(task_id, captured_at);
CREATE TABLE IF NOT EXISTS calendar_snapshot(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  captured_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cs_task ON calendar_snapshot(task_id, captured_at);
CREATE TABLE IF NOT EXISTS alert_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  price REAL,
  notified_at TEXT NOT NULL,
  channel TEXT
);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)
        # lightweight migrations for existing databases
        for table, col, ddl in (
            ("monitor_task", "flight_no",
             "ALTER TABLE monitor_task ADD COLUMN flight_no TEXT"),
            ("price_record", "flight_no",
             "ALTER TABLE price_record ADD COLUMN flight_no TEXT"),
        ):
            cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                db.execute(ddl)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

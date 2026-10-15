import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone


class ReminderDedup:
    """提醒去重表。dedup_key 语义见 reminder.py 各规则注释。"""

    def __init__(self, db_path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS notified ("
            " rule_key TEXT PRIMARY KEY, sent_at TEXT NOT NULL)")
        self._conn.execute('CREATE TABLE IF NOT EXISTS notification_claims(rule_key TEXT PRIMARY KEY, lease TEXT NOT NULL, expires REAL NOT NULL)')
        self._conn.commit()

    def claim(self, rule_key: str) -> str | None:
        with self._lock:
            self._conn.execute('BEGIN IMMEDIATE')
            try:
                if self._conn.execute('SELECT 1 FROM notified WHERE rule_key=?', (rule_key,)).fetchone():
                    self._conn.commit()
                    return None
                now, lease = time.time(), uuid.uuid4().hex
                row = self._conn.execute('SELECT expires FROM notification_claims WHERE rule_key=?', (rule_key,)).fetchone()
                if row and row[0] > now:
                    self._conn.commit()
                    return None
                self._conn.execute('INSERT INTO notification_claims VALUES(?,?,?) ON CONFLICT(rule_key) DO UPDATE SET lease=excluded.lease,expires=excluded.expires', (rule_key,lease,now+300))
                self._conn.commit()
                return lease
            except BaseException:
                self._conn.rollback()
                raise

    def finish(self, rule_key: str, lease: str, success: bool) -> bool:
        with self._lock:
            self._conn.execute('BEGIN IMMEDIATE')
            try:
                row = self._conn.execute('SELECT 1 FROM notification_claims WHERE rule_key=? AND lease=? AND expires>=?', (rule_key,lease,time.time())).fetchone()
                if not row:
                    self._conn.commit()
                    return False
                if success:
                    self._conn.execute('INSERT INTO notified VALUES(?,?) ON CONFLICT(rule_key) DO NOTHING', (rule_key,datetime.now(timezone.utc).isoformat()))
                self._conn.execute('DELETE FROM notification_claims WHERE rule_key=? AND lease=?', (rule_key,lease))
                self._conn.commit()
                return success
            except BaseException:
                self._conn.rollback()
                raise

    def already_sent(self, rule_key: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM notified WHERE rule_key = ?", (rule_key,)).fetchone()
        return row is not None

    def mark_sent(self, rule_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO notified (rule_key, sent_at) VALUES (?, ?)"
                " ON CONFLICT(rule_key) DO NOTHING",
                (rule_key, datetime.now(timezone.utc).isoformat()))
            self._conn.commit()

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_FILENAME = "ai_os_memory.db"


class TemporalStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = db_path or str(base_dir / DB_FILENAME)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _column_names(self, conn: sqlite3.Connection, table: str) -> List[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [str(r["name"]) for r in rows]

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temporal_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local-dev',
                    task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    run_at_epoch INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    error TEXT,
                    locked_at TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                """
            )

            cols = self._column_names(conn, "temporal_tasks")

            # Backfill missing columns for older DBs
            if "user_id" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local-dev'")
            if "task_id" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN task_id TEXT NOT NULL DEFAULT ''")
            if "kind" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'run_task'")
            if "payload_json" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'")
            if "run_at_epoch" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN run_at_epoch INTEGER NOT NULL DEFAULT 0")
            if "status" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'queued'")
            if "error" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN error TEXT")
            if "locked_at" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN locked_at TEXT")
            if "created_at" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN created_at TEXT")
            if "updated_at" not in cols:
                conn.execute("ALTER TABLE temporal_tasks ADD COLUMN updated_at TEXT")

            # Backfill null timestamps in legacy rows
            conn.execute("UPDATE temporal_tasks SET created_at = datetime('now') WHERE created_at IS NULL")
            conn.execute("UPDATE temporal_tasks SET updated_at = datetime('now') WHERE updated_at IS NULL")
            conn.execute("UPDATE temporal_tasks SET status = 'queued' WHERE status IS NULL OR status = ''")
            conn.execute("UPDATE temporal_tasks SET user_id = 'local-dev' WHERE user_id IS NULL OR user_id = ''")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_temporal_tasks_user_status_runat ON temporal_tasks(user_id, status, run_at_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_temporal_tasks_task_id ON temporal_tasks(task_id)"
            )

    def create_task(
        self,
        *,
        user_id: str,
        task_id: str,
        kind: str,
        payload_json: str,
        run_at_epoch: int,
    ) -> int:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO temporal_tasks(
                    user_id, task_id, kind, payload_json, run_at_epoch, status, error, locked_at, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, 'queued', NULL, NULL, ?, ?)
                """,
                (user_id, task_id, kind, payload_json, int(run_at_epoch), now, now),
            )
            return int(cur.lastrowid)

    def list_due(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        now_epoch = int(time.time())
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, task_id, kind, payload_json, run_at_epoch, status, error, locked_at, created_at, updated_at
                FROM temporal_tasks
                WHERE status='queued' AND run_at_epoch <= ?
                ORDER BY run_at_epoch ASC, id ASC
                LIMIT ?
                """,
                (now_epoch, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_tasks(self, *, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, task_id, kind, payload_json, run_at_epoch, status, error, locked_at, created_at, updated_at
                FROM temporal_tasks
                WHERE user_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_done(self, *, task_row_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE temporal_tasks
                SET status='done', updated_at=datetime('now')
                WHERE id=?
                """,
                (int(task_row_id),),
            )

    def mark_failed(self, *, task_row_id: int, error: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE temporal_tasks
                SET status='failed', error=?, updated_at=datetime('now')
                WHERE id=?
                """,
                (str(error), int(task_row_id)),
            )

    def run_due_once(self, *, limit: int = 20) -> int:
        return len(self.list_due(limit=limit))


temporal_store = TemporalStore()

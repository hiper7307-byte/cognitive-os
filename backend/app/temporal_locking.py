from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DB_FILENAME = "ai_os_memory.db"


class TemporalLocking:
    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = db_path or str(base_dir / DB_FILENAME)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def claim_task(self, *, task_row_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE temporal_tasks
                SET status='running', locked_at=datetime('now')
                WHERE id=? AND status='queued'
                """,
                (task_row_id,),
            )
            return cur.rowcount == 1


temporal_locking = TemporalLocking()

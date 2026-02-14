from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


DB_FILENAME = "ai_os_memory.db"


class IdempotencyStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = db_path or str(base_dir / DB_FILENAME)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    status_code INTEGER NOT NULL DEFAULT 200,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, endpoint, idem_key)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_idem_user_endpoint ON idempotency_keys(user_id, endpoint)"
            )

    def get(
        self, *, user_id: str, endpoint: str, idem_key: str
    ) -> Optional[Tuple[Dict[str, Any], int, str]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT response_json, status_code, request_hash
                FROM idempotency_keys
                WHERE user_id=? AND endpoint=? AND idem_key=?
                """,
                (user_id, endpoint, idem_key),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["response_json"]), int(row["status_code"]), str(row["request_hash"])

    def put(
        self,
        *,
        user_id: str,
        endpoint: str,
        idem_key: str,
        request_hash: str,
        response: Dict[str, Any],
        status_code: int = 200,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO idempotency_keys(user_id, endpoint, idem_key, request_hash, response_json, status_code)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, endpoint, idem_key) DO UPDATE SET
                    request_hash=excluded.request_hash,
                    response_json=excluded.response_json,
                    status_code=excluded.status_code
                """,
                (
                    user_id,
                    endpoint,
                    idem_key,
                    request_hash,
                    json.dumps(response, ensure_ascii=False),
                    int(status_code),
                ),
            )


idempotency_store = IdempotencyStore()

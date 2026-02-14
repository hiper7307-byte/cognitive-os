from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(len(a)):
        x = float(a[i])
        y = float(b[i])
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class VectorStore:
    """
    SQLite-backed vector index.
    IMPORTANT: This module must NOT import memory_service (avoids circular import).
    """

    def __init__(self, db_path: str | Path = "ai_os_memory.db") -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local-dev',
                    namespace TEXT NOT NULL DEFAULT 'memory',
                    memory_id INTEGER NOT NULL,
                    memory_type TEXT,
                    model TEXT,
                    dim INTEGER,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, namespace, memory_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_user_namespace
                ON vector_index(user_id, namespace)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_memory_id
                ON vector_index(memory_id)
                """
            )
            conn.commit()

    def upsert(
        self,
        *,
        user_id: str,
        memory_id: int,
        namespace: str,
        model: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        memory_type = None
        if metadata:
            memory_type = metadata.get("memory_type")

        payload = json.dumps(vector, ensure_ascii=False)
        dim = len(vector)
        now = _utc_now_iso()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO vector_index (
                    user_id, namespace, memory_id, memory_type, model, dim, vector_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, namespace, memory_id) DO UPDATE SET
                    memory_type=excluded.memory_type,
                    model=excluded.model,
                    dim=excluded.dim,
                    vector_json=excluded.vector_json,
                    created_at=excluded.created_at
                """,
                (
                    user_id,
                    namespace,
                    int(memory_id),
                    memory_type,
                    model,
                    int(dim),
                    payload,
                    now,
                ),
            )
            conn.commit()

    def search(
        self,
        *,
        user_id: str,
        query_vector: List[float],
        namespace: str = "memory",
        model: Optional[str] = None,
        top_k: int = 8,
        memory_types: Optional[List[str]] = None,
    ) -> List[Tuple[int, float]]:
        if not query_vector:
            return []

        sql = """
            SELECT memory_id, memory_type, model, vector_json
            FROM vector_index
            WHERE user_id = ?
              AND namespace = ?
        """
        params: List[Any] = [user_id, namespace]

        if model:
            sql += " AND model = ?"
            params.append(model)

        if memory_types:
            placeholders = ",".join(["?"] * len(memory_types))
            sql += f" AND (memory_type IN ({placeholders}))"
            params.extend(memory_types)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        scored: List[Tuple[int, float]] = []
        for row in rows:
            try:
                vec = json.loads(row["vector_json"])
                score = _cosine_similarity(query_vector, vec)
                scored.append((int(row["memory_id"]), float(score)))
            except Exception:
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: max(1, int(top_k))]

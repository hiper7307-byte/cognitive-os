from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple


def _utc_epoch() -> int:
    return int(time.time())


class DynamicsStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_dynamics (
                    memory_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    reference_count INTEGER NOT NULL DEFAULT 0,
                    last_referenced_epoch INTEGER,
                    last_decay_epoch INTEGER,
                    confidence_override REAL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY (memory_id, user_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    left_memory_id INTEGER NOT NULL,
                    right_memory_id INTEGER NOT NULL,
                    relation TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    score REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at_epoch INTEGER NOT NULL,
                    resolved_at_epoch INTEGER,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(user_id, left_memory_id, right_memory_id, relation)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_lineage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    from_memory_id INTEGER NOT NULL,
                    to_memory_id INTEGER NOT NULL,
                    relation TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(user_id, from_memory_id, to_memory_id, relation)
                )
                """
            )
            conn.commit()

    def touch_memory_row(self, *, user_id: str, memory_id: int) -> None:
        now = _utc_epoch()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_dynamics (
                    memory_id, user_id, reference_count, last_referenced_epoch, last_decay_epoch,
                    confidence_override, created_at_epoch, updated_at_epoch
                )
                VALUES (?, ?, 0, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(memory_id, user_id) DO UPDATE SET
                    updated_at_epoch=excluded.updated_at_epoch
                """,
                (memory_id, user_id, now, now),
            )
            conn.commit()

    def increment_reference(self, *, user_id: str, memory_id: int, by: int = 1) -> Dict[str, Any]:
        now = _utc_epoch()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_dynamics (
                    memory_id, user_id, reference_count, last_referenced_epoch, last_decay_epoch,
                    confidence_override, created_at_epoch, updated_at_epoch
                )
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(memory_id, user_id) DO UPDATE SET
                    reference_count = memory_dynamics.reference_count + ?,
                    last_referenced_epoch = excluded.last_referenced_epoch,
                    updated_at_epoch = excluded.updated_at_epoch
                """,
                (memory_id, user_id, by, now, now, now, by),
            )
            row = conn.execute(
                """
                SELECT memory_id, user_id, reference_count, last_referenced_epoch, last_decay_epoch,
                       confidence_override, created_at_epoch, updated_at_epoch
                FROM memory_dynamics
                WHERE memory_id=? AND user_id=?
                """,
                (memory_id, user_id),
            ).fetchone()
            conn.commit()
        return dict(row) if row else {}

    def list_semantic_memories(self, *, user_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.id AS memory_id,
                    m.user_id,
                    m.memory_type,
                    m.content,
                    m.confidence,
                    m.created_at,
                    m.updated_at,
                    COALESCE(d.reference_count, 0) AS reference_count,
                    d.last_referenced_epoch,
                    d.last_decay_epoch,
                    d.confidence_override
                FROM memories m
                LEFT JOIN memory_dynamics d
                  ON d.memory_id = m.id AND d.user_id = m.user_id
                WHERE m.user_id=?
                  AND m.memory_type='semantic'
                  AND COALESCE(m.is_deleted, 0)=0
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_memory_confidence(self, *, user_id: str, memory_id: int, confidence: float) -> None:
        now = _utc_epoch()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE memories
                SET confidence=?, updated_at=?
                WHERE user_id=? AND id=?
                """,
                (confidence, now, user_id, memory_id),
            )
            conn.execute(
                """
                INSERT INTO memory_dynamics (
                    memory_id, user_id, reference_count, last_referenced_epoch, last_decay_epoch,
                    confidence_override, created_at_epoch, updated_at_epoch
                )
                VALUES (?, ?, 0, NULL, ?, ?, ?, ?)
                ON CONFLICT(memory_id, user_id) DO UPDATE SET
                    last_decay_epoch=excluded.last_decay_epoch,
                    confidence_override=excluded.confidence_override,
                    updated_at_epoch=excluded.updated_at_epoch
                """,
                (memory_id, user_id, now, confidence, now, now),
            )
            conn.commit()

    def upsert_conflict(
        self,
        *,
        user_id: str,
        left_memory_id: int,
        right_memory_id: int,
        relation: str,
        reason: str,
        score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = _utc_epoch()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_conflicts (
                    user_id, left_memory_id, right_memory_id, relation, reason, score,
                    status, created_at_epoch, resolved_at_epoch, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, NULL, ?)
                ON CONFLICT(user_id, left_memory_id, right_memory_id, relation) DO UPDATE SET
                    reason=excluded.reason,
                    score=excluded.score,
                    status='open',
                    metadata_json=excluded.metadata_json
                """,
                (user_id, left_memory_id, right_memory_id, relation, reason, score, now, metadata_json),
            )
            row = conn.execute(
                """
                SELECT id FROM memory_conflicts
                WHERE user_id=? AND left_memory_id=? AND right_memory_id=? AND relation=?
                """,
                (user_id, left_memory_id, right_memory_id, relation),
            ).fetchone()
            conn.commit()
        return int(row["id"]) if row else 0

    def link_lineage(
        self,
        *,
        user_id: str,
        from_memory_id: int,
        to_memory_id: int,
        relation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = _utc_epoch()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_lineage (
                    user_id, from_memory_id, to_memory_id, relation, created_at_epoch, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, from_memory_id, to_memory_id, relation) DO UPDATE SET
                    metadata_json=excluded.metadata_json
                """,
                (user_id, from_memory_id, to_memory_id, relation, now, metadata_json),
            )
            row = conn.execute(
                """
                SELECT id FROM memory_lineage
                WHERE user_id=? AND from_memory_id=? AND to_memory_id=? AND relation=?
                """,
                (user_id, from_memory_id, to_memory_id, relation),
            ).fetchone()
            conn.commit()
        return int(row["id"]) if row else 0

    def list_conflicts(self, *, user_id: str, status: Optional[str], limit: int) -> List[Dict[str, Any]]:
        where = "WHERE user_id=?"
        params: List[Any] = [user_id]
        if status:
            where += " AND status=?"
            params.append(status)
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT id, user_id, left_memory_id, right_memory_id, relation, reason, score,
                       status, created_at_epoch, resolved_at_epoch, metadata_json
                FROM memory_conflicts
                {where}
                ORDER BY id DESC
                LIMIT ?
                """
            ,
                tuple(params),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
            except Exception:
                d["metadata"] = {}
            out.append(d)
        return out

    def resolve_conflict(self, *, user_id: str, conflict_id: int) -> bool:
        now = _utc_epoch()
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE memory_conflicts
                SET status='resolved', resolved_at_epoch=?
                WHERE id=? AND user_id=?
                """,
                (now, conflict_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

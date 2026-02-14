from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DB_FILENAME = "ai_os_memory.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    id: int
    user_id: str
    memory_type: str
    content: str
    metadata: Dict[str, Any]
    source_task_id: Optional[str]
    confidence: float
    is_deleted: bool
    retention_until: Optional[str]
    corrected_by_memory_id: Optional[int]
    created_at: str
    updated_at: str


class MemoryStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = str(base_dir / DB_FILENAME) if db_path is None else db_path
        self._init_db()
        self._migrate_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> List[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [str(r["name"]) for r in rows]

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local-dev',
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    source_task_id TEXT,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    retention_until TEXT,
                    corrected_by_memory_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    memory_id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local-dev',
                    model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_id INTEGER NOT NULL,
                    revision_no INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    change_kind TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(content, content='memories', content_rowid='id');
                """
            )

            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
                    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                END;
                """
            )

    def _migrate_schema(self) -> None:
        with self._conn() as conn:
            mem_cols = self._table_columns(conn, "memories")
            if "user_id" not in mem_cols:
                conn.execute("ALTER TABLE memories ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local-dev'")
            if "confidence" not in mem_cols:
                conn.execute("ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 0.5")
            if "is_deleted" not in mem_cols:
                conn.execute("ALTER TABLE memories ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")
            if "retention_until" not in mem_cols:
                conn.execute("ALTER TABLE memories ADD COLUMN retention_until TEXT")
            if "corrected_by_memory_id" not in mem_cols:
                conn.execute("ALTER TABLE memories ADD COLUMN corrected_by_memory_id INTEGER")

            emb_cols = self._table_columns(conn, "memory_embeddings")
            if "user_id" not in emb_cols:
                conn.execute("ALTER TABLE memory_embeddings ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local-dev'")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_deleted ON memories(user_id, is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_retention ON memories(user_id, retention_until)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_id ON memory_embeddings(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_revisions_user_memory ON memory_revisions(user_id, memory_id, revision_no DESC)")

            conn.execute("UPDATE memories SET user_id='local-dev' WHERE user_id IS NULL OR user_id = ''")
            conn.execute("UPDATE memory_embeddings SET user_id='local-dev' WHERE user_id IS NULL OR user_id = ''")

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            memory_type=str(row["memory_type"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            source_task_id=row["source_task_id"],
            confidence=float(row["confidence"]),
            is_deleted=bool(int(row["is_deleted"])),
            retention_until=row["retention_until"],
            corrected_by_memory_id=row["corrected_by_memory_id"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _next_revision_no(self, conn: sqlite3.Connection, *, user_id: str, memory_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(revision_no), 0) AS m FROM memory_revisions WHERE user_id=? AND memory_id=?",
            (user_id, memory_id),
        ).fetchone()
        return int(row["m"]) + 1

    def _append_revision(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str,
        memory_id: int,
        content: str,
        metadata: Dict[str, Any],
        confidence: float,
        change_kind: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO memory_revisions(user_id, memory_id, revision_no, content, metadata_json, confidence, change_kind, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                memory_id,
                self._next_revision_no(conn, user_id=user_id, memory_id=memory_id),
                content,
                json.dumps(metadata, ensure_ascii=False),
                float(confidence),
                change_kind,
                utc_now_iso(),
            ),
        )

    def write_memory(
        self,
        *,
        user_id: str,
        memory_type: str,
        content: str,
        source_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
        retention_until: Optional[str] = None,
    ) -> int:
        now = utc_now_iso()
        md = metadata or {}
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories (
                    user_id, memory_type, content, metadata_json, source_task_id,
                    confidence, is_deleted, retention_until, corrected_by_memory_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)
                """,
                (
                    user_id,
                    memory_type,
                    content,
                    json.dumps(md, ensure_ascii=False),
                    source_task_id,
                    float(confidence),
                    retention_until,
                    now,
                    now,
                ),
            )
            memory_id = int(cur.lastrowid)
            self._append_revision(
                conn,
                user_id=user_id,
                memory_id=memory_id,
                content=content,
                metadata=md,
                confidence=confidence,
                change_kind="create",
            )
            return memory_id

    def update_memory(
        self,
        *,
        user_id: str,
        memory_id: int,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        retention_until: Optional[str] = None,
    ) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id=? AND user_id=? AND is_deleted=0",
                (memory_id, user_id),
            ).fetchone()
            if not row:
                return False

            new_content = row["content"] if content is None else content
            old_md = json.loads(row["metadata_json"] or "{}")
            new_md = old_md if metadata is None else metadata
            new_conf = float(row["confidence"]) if confidence is None else float(confidence)
            new_ret = row["retention_until"] if retention_until is None else retention_until

            conn.execute(
                """
                UPDATE memories
                SET content=?, metadata_json=?, confidence=?, retention_until=?, updated_at=?
                WHERE id=? AND user_id=?
                """,
                (
                    new_content,
                    json.dumps(new_md, ensure_ascii=False),
                    new_conf,
                    new_ret,
                    utc_now_iso(),
                    memory_id,
                    user_id,
                ),
            )
            self._append_revision(
                conn,
                user_id=user_id,
                memory_id=memory_id,
                content=new_content,
                metadata=new_md,
                confidence=new_conf,
                change_kind="update",
            )
            return True

    def correct_memory(
        self,
        *,
        user_id: str,
        memory_id: int,
        corrected_content: str,
        correction_metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 0.75,
    ) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id=? AND user_id=? AND is_deleted=0",
                (memory_id, user_id),
            ).fetchone()
            if not row:
                return None

            new_md = dict(json.loads(row["metadata_json"] or "{}"))
            new_md["corrected_from_memory_id"] = int(memory_id)
            if correction_metadata:
                new_md["correction"] = correction_metadata

            now = utc_now_iso()
            cur = conn.execute(
                """
                INSERT INTO memories (
                    user_id, memory_type, content, metadata_json, source_task_id,
                    confidence, is_deleted, retention_until, corrected_by_memory_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)
                """,
                (
                    user_id,
                    row["memory_type"],
                    corrected_content,
                    json.dumps(new_md, ensure_ascii=False),
                    row["source_task_id"],
                    float(confidence),
                    row["retention_until"],
                    now,
                    now,
                ),
            )
            new_id = int(cur.lastrowid)

            conn.execute(
                """
                UPDATE memories
                SET corrected_by_memory_id=?, updated_at=?
                WHERE id=? AND user_id=?
                """,
                (new_id, now, memory_id, user_id),
            )

            self._append_revision(
                conn,
                user_id=user_id,
                memory_id=memory_id,
                content=row["content"],
                metadata=json.loads(row["metadata_json"] or "{}"),
                confidence=float(row["confidence"]),
                change_kind="corrected_out",
            )
            self._append_revision(
                conn,
                user_id=user_id,
                memory_id=new_id,
                content=corrected_content,
                metadata=new_md,
                confidence=float(confidence),
                change_kind="corrected_in",
            )
            return new_id

    def soft_delete_memory(self, *, user_id: str, memory_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id=? AND user_id=? AND is_deleted=0",
                (memory_id, user_id),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE memories SET is_deleted=1, updated_at=? WHERE id=? AND user_id=?",
                (utc_now_iso(), memory_id, user_id),
            )
            self._append_revision(
                conn,
                user_id=user_id,
                memory_id=memory_id,
                content=row["content"],
                metadata=json.loads(row["metadata_json"] or "{}"),
                confidence=float(row["confidence"]),
                change_kind="soft_delete",
            )
            return True

    def purge_expired(self, *, user_id: str, now_iso: Optional[str] = None) -> int:
        ts = now_iso or utc_now_iso()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id FROM memories
                WHERE user_id=? AND is_deleted=0 AND retention_until IS NOT NULL AND retention_until <= ?
                """,
                (user_id, ts),
            ).fetchall()
            ids = [int(r["id"]) for r in rows]
            for mid in ids:
                conn.execute("UPDATE memories SET is_deleted=1, updated_at=? WHERE id=? AND user_id=?", (ts, mid, user_id))
            return len(ids)

    def upsert_embedding(self, *, user_id: str, memory_id: int, model: str, vector: List[float]) -> None:
        now = utc_now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_embeddings(memory_id, user_id, model, vector_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    model=excluded.model,
                    vector_json=excluded.vector_json,
                    updated_at=excluded.updated_at
                """,
                (memory_id, user_id, model, json.dumps(vector), now, now),
            )

    def get_memory(self, *, user_id: str, memory_id: int, include_deleted: bool = False) -> Optional[MemoryRecord]:
        with self._conn() as conn:
            if include_deleted:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id=? AND user_id=?",
                    (memory_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id=? AND user_id=? AND is_deleted=0",
                    (memory_id, user_id),
                ).fetchone()
            return self._row_to_record(row) if row else None

    def recent_memories(self, *, user_id: str, memory_type: Optional[str] = None, limit: int = 20) -> List[MemoryRecord]:
        limit = max(1, min(limit, 500))
        with self._conn() as conn:
            if memory_type:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE user_id=? AND is_deleted=0 AND memory_type=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, memory_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE user_id=? AND is_deleted=0
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def query_memories(
        self,
        *,
        user_id: str,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        q = (query or "").strip()
        if not q:
            return []

        limit = max(1, min(limit, 500))
        like_q = f"%{q}%"

        sql = """
            SELECT m.*
            FROM memories m
            WHERE m.user_id = ?
              AND m.is_deleted = 0
              AND m.content LIKE ?
        """
        params: List[Any] = [user_id, like_q]

        if memory_types:
            placeholders = ",".join("?" for _ in memory_types)
            sql += f" AND m.memory_type IN ({placeholders})"
            params.extend(memory_types)

        sql += " ORDER BY m.id DESC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def query_by_vector(
        self,
        *,
        user_id: str,
        query_vector: List[float],
        model: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        limit = max(1, min(limit, 500))

        def dot(a: Iterable[float], b: Iterable[float]) -> float:
            return float(sum(x * y for x, y in zip(a, b)))

        def norm(a: Iterable[float]) -> float:
            return float(sum(x * x for x in a)) ** 0.5

        qn = norm(query_vector)
        if qn == 0:
            return []

        with self._conn() as conn:
            if memory_types:
                placeholders = ",".join("?" for _ in memory_types)
                rows = conn.execute(
                    f"""
                    SELECT m.*, e.vector_json
                    FROM memories m
                    JOIN memory_embeddings e ON e.memory_id = m.id
                    WHERE e.user_id = ?
                      AND e.model = ?
                      AND m.user_id = ?
                      AND m.is_deleted = 0
                      AND m.memory_type IN ({placeholders})
                    """,
                    [user_id, model, user_id, *memory_types],
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.*, e.vector_json
                    FROM memories m
                    JOIN memory_embeddings e ON e.memory_id = m.id
                    WHERE e.user_id = ?
                      AND e.model = ?
                      AND m.user_id = ?
                      AND m.is_deleted = 0
                    """,
                    (user_id, model, user_id),
                ).fetchall()

        scored: List[tuple[float, sqlite3.Row]] = []
        for r in rows:
            vec = json.loads(r["vector_json"])
            vn = norm(vec)
            if vn == 0:
                continue
            score = dot(query_vector, vec) / (qn * vn)
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [r for _, r in scored[:limit]]
        return [self._row_to_record(r) for r in top]

    def memory_revisions(self, *, user_id: str, memory_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, memory_id, revision_no, content, metadata_json, confidence, change_kind, changed_at
                FROM memory_revisions
                WHERE user_id=? AND memory_id=?
                ORDER BY revision_no DESC
                LIMIT ?
                """,
                (user_id, memory_id, limit),
            ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "user_id": r["user_id"],
                "memory_id": int(r["memory_id"]),
                "revision_no": int(r["revision_no"]),
                "content": r["content"],
                "metadata": json.loads(r["metadata_json"] or "{}"),
                "confidence": float(r["confidence"]),
                "change_kind": r["change_kind"],
                "changed_at": r["changed_at"],
            }
            for r in rows
        ]

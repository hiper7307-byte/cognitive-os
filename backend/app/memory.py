from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .embedding_provider import embedding_provider
from .memory_store import MemoryRecord, MemoryStore
from .vector_store import VectorStore


class MemoryService:
    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self.store = store or MemoryStore()
        self.vector_store = VectorStore(self.store.db_path)
        self.embedding_model_name = embedding_provider.model_name
        self.namespace = "memory"

    def write(
        self,
        *,
        user_id: str,
        memory_type: str,
        content: str,
        source_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embed: bool = True,
        confidence: float = 0.5,
        retention_until: Optional[str] = None,
    ) -> int:
        memory_id = self.store.write_memory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            source_task_id=source_task_id,
            metadata=metadata or {},
            confidence=confidence,
            retention_until=retention_until,
        )
        if embed:
            self._embed_memory(
                user_id=user_id,
                memory_id=memory_id,
                text=content,
                memory_type=memory_type,
                source_task_id=source_task_id,
            )
        return memory_id

    def _embed_memory(
        self,
        *,
        user_id: str,
        memory_id: int,
        text: str,
        memory_type: str,
        source_task_id: Optional[str],
    ) -> None:
        try:
            vector = embedding_provider.embed(text)
            self.store.upsert_embedding(
                user_id=user_id,
                memory_id=memory_id,
                model=self.embedding_model_name,
                vector=vector,
            )
            self.vector_store.upsert(
                user_id=user_id,
                memory_id=memory_id,
                namespace=self.namespace,
                model=self.embedding_model_name,
                vector=vector,
                metadata={
                    "memory_type": memory_type,
                    "source_task_id": source_task_id,
                },
            )
        except Exception:
            return

    def write_task_event(
        self,
        *,
        user_id: str,
        task_id: str,
        intent: str,
        user_input: str,
        outcome: str,
        executor: str,
        status: str = "success",
        extra: Optional[Dict[str, Any]] = None,
        confidence: float = 0.7,
    ) -> int:
        payload = {
            "intent": intent,
            "user_input": user_input,
            "outcome": outcome,
            "executor": executor,
            "status": status,
            **(extra or {}),
        }
        content = f"[task:{task_id}] intent={intent} outcome={outcome}"
        return self.write(
            user_id=user_id,
            memory_type="episodic",
            content=content,
            source_task_id=task_id,
            metadata=payload,
            embed=True,
            confidence=confidence,
        )

    def write_procedural_rule(
        self,
        *,
        user_id: str,
        rule_text: str,
        source_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 0.8,
    ) -> int:
        return self.write(
            user_id=user_id,
            memory_type="procedural",
            content=rule_text,
            source_task_id=source_task_id,
            metadata=metadata or {},
            embed=True,
            confidence=confidence,
        )

    def write_semantic_fact(
        self,
        *,
        user_id: str,
        fact_text: str,
        source_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 0.75,
    ) -> int:
        return self.write(
            user_id=user_id,
            memory_type="semantic",
            content=fact_text,
            source_task_id=source_task_id,
            metadata=metadata or {},
            embed=True,
            confidence=confidence,
        )

    def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        lexical_rows = self.store.query_memories(
            user_id=user_id,
            query=query,
            memory_types=memory_types,
            limit=limit,
        )

        semantic_rows: List[MemoryRecord] = []
        try:
            qvec = embedding_provider.embed(query)
            ranked = self.vector_store.search(
                user_id=user_id,
                query_vector=qvec,
                namespace=self.namespace,
                model=self.embedding_model_name,
                top_k=limit,
                memory_types=memory_types,
            )
            ids = [memory_id for memory_id, _score in ranked]
            fetched = [self.store.get_memory(user_id=user_id, memory_id=mid) for mid in ids]
            semantic_rows = [x for x in fetched if x is not None]
        except Exception:
            semantic_rows = []

        merged: Dict[int, MemoryRecord] = {}
        for r in semantic_rows:
            merged[r.id] = r
        for r in lexical_rows:
            if r.id not in merged:
                merged[r.id] = r

        ordered = list(merged.values())[:limit]
        return [self._record_to_dict(r) for r in ordered]

    def recent(
        self,
        *,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        rows = self.store.recent_memories(user_id=user_id, memory_type=memory_type, limit=limit)
        return [self._record_to_dict(r) for r in rows]

    def get(self, *, user_id: str, memory_id: int) -> Optional[Dict[str, Any]]:
        row = self.store.get_memory(user_id=user_id, memory_id=memory_id)
        return self._record_to_dict(row) if row else None

    def _record_to_dict(self, row: MemoryRecord) -> Dict[str, Any]:
        return asdict(row)


memory_service = MemoryService()


def new_task_id() -> str:
    return str(uuid.uuid4())

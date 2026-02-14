from __future__ import annotations

from app.embedding_provider import embedding_provider
from app.memory_store import MemoryStore
from app.vector_store import VectorStore


def main() -> None:
    store = MemoryStore()
    vstore = VectorStore(store.db_path)

    rows = store.recent_memories(memory_type=None, limit=100000)
    count = 0
    for row in rows:
        vec = embedding_provider.embed(row.content)
        vstore.upsert(
            memory_id=row.id,
            namespace="memory",
            model=embedding_provider.model_name,
            vector=vec,
            metadata={
                "memory_type": row.memory_type,
                "source_task_id": row.source_task_id,
            },
        )
        count += 1

    print(f"reindexed_vectors={count}")
    print(f"model={embedding_provider.model_name}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import os

from .graph_linker import GraphLinker
from .graph_service import GraphService
from .graph_store import GraphStore

_DB_PATH = os.getenv("AI_OS_DB_PATH", os.path.join("app", "ai_os_memory.db"))

graph_store = GraphStore(db_path=_DB_PATH)
graph_linker = GraphLinker(store=graph_store)
graph_service = GraphService(store=graph_store, linker=graph_linker)

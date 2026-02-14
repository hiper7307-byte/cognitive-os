from __future__ import annotations

import os
from pathlib import Path

from .arbitration_models import ArbitrationConfig
from .arbitration_service import ArbitrationService

from .dynamics_models import DynamicsConfig
from .dynamics_service import MemoryDynamicsService
from .dynamics_store import DynamicsStore

from .identity_models import IdentityConfig
from .identity_service import IdentityAlignmentService
from .identity_store import IdentityAlignmentStore

from .graph_linker import GraphLinker
from .graph_store import GraphStore

from .meta_eval_service import MetaEvalService
from .meta_eval_store import MetaEvalStore


def _resolve_db_path() -> str:
    env_path = (os.getenv("AI_OS_DB_PATH") or "").strip()
    if env_path:
        return env_path

    rel_default = Path("app") / "ai_os_memory.db"
    if rel_default.exists():
        return str(rel_default)

    pkg_default = Path(__file__).resolve().parent.parent / "ai_os_memory.db"
    return str(pkg_default)


DB_PATH = _resolve_db_path()

# Stores
dynamics_store = DynamicsStore(db_path=DB_PATH)
identity_alignment_store = IdentityAlignmentStore(db_path=DB_PATH)
graph_store = GraphStore(db_path=DB_PATH)
meta_eval_store = MetaEvalStore(db_path=DB_PATH)

# Services
dynamics_service = MemoryDynamicsService(
    store=dynamics_store,
    config=DynamicsConfig(),
)

# If your IdentityAlignmentService constructor expects "store=" keep this.
# If it expects "identity_store=", switch to identity_store=identity_alignment_store.
identity_alignment_service = IdentityAlignmentService(
    store=identity_alignment_store,
    config=IdentityConfig(),
)

graph_linker = GraphLinker(store=graph_store)

arbitration_service = ArbitrationService(
    config=ArbitrationConfig(),
    identity_alignment_service=identity_alignment_service,
)

meta_eval_service = MetaEvalService(store=meta_eval_store)

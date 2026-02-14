import sqlite3
from pathlib import Path

db = Path(r".\backend\ai_os_memory.db").resolve()
print(f"USING DB: {db}")

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

def cols(table: str):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def ensure_col(table: str, coldef: str):
    name = coldef.split()[0]
    if name not in cols(table):
        print(f"ADD COLUMN {table}.{name}")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")

# tables
conn.execute("""
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL DEFAULT 'local-dev',
  memory_type TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT,
  source_task_id TEXT,
  confidence REAL NOT NULL DEFAULT 1.0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  retention_until TEXT,
  created_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT ''
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS vector_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL DEFAULT 'local-dev',
  namespace TEXT NOT NULL DEFAULT 'memory',
  memory_id INTEGER NOT NULL,
  memory_type TEXT,
  model TEXT,
  dim INTEGER,
  vector_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT '',
  UNIQUE(user_id, namespace, memory_id)
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS temporal_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL DEFAULT 'local-dev',
  task_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  run_at_epoch INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  locked_at TEXT,
  locked_by TEXT,
  error TEXT,
  idempotency_key TEXT,
  created_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT ''
)
""")

# add/repair columns
for c in [
    "user_id TEXT NOT NULL DEFAULT 'local-dev'",
    "memory_type TEXT",
    "model TEXT",
    "dim INTEGER",
    "created_at TEXT NOT NULL DEFAULT ''",
]:
    ensure_col("vector_index", c)

for c in [
    "confidence REAL NOT NULL DEFAULT 1.0",
    "is_deleted INTEGER NOT NULL DEFAULT 0",
    "retention_until TEXT",
]:
    ensure_col("memories", c)

for c in [
    "user_id TEXT NOT NULL DEFAULT 'local-dev'",
    "status TEXT NOT NULL DEFAULT 'queued'",
    "locked_at TEXT",
    "locked_by TEXT",
    "error TEXT",
    "idempotency_key TEXT",
    "created_at TEXT NOT NULL DEFAULT ''",
    "updated_at TEXT NOT NULL DEFAULT ''",
]:
    ensure_col("temporal_tasks", c)

# normalize timestamps
conn.execute("UPDATE memories SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
conn.execute("UPDATE memories SET updated_at = datetime('now') WHERE updated_at IS NULL OR updated_at = ''")
conn.execute("UPDATE vector_index SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
conn.execute("UPDATE temporal_tasks SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
conn.execute("UPDATE temporal_tasks SET updated_at = datetime('now') WHERE updated_at IS NULL OR updated_at = ''")

# indexes
conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_type_created ON memories(user_id, memory_type, created_at DESC)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_user_namespace ON vector_index(user_id, namespace)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_temporal_user_status_runat ON temporal_tasks(user_id, status, run_at_epoch)")

conn.commit()
print("Schema repair complete.")

for t in ["memories","vector_index","temporal_tasks"]:
    print(f"\n[{t}]")
    for r in conn.execute(f"PRAGMA table_info({t})"):
        print(f"- {r['name']} {r['type']}")

conn.close()

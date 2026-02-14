import os
import sqlite3
import time

db_path = os.getenv("AI_OS_DB_PATH", os.path.join("app", "ai_os_memory.db"))
print(f"DB: {db_path}")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS identity_profiles (
    user_id TEXT PRIMARY KEY,
    values_json TEXT NOT NULL DEFAULT '[]',
    goals_json TEXT NOT NULL DEFAULT '[]',
    constraints_json TEXT NOT NULL DEFAULT '[]',
    risk_tolerance REAL NOT NULL DEFAULT 0.5,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at_epoch INTEGER NOT NULL DEFAULT 0
)
""")
conn.commit()

cols = {r["name"] for r in cur.execute("PRAGMA table_info(identity_profiles)").fetchall()}
print("Existing columns:", sorted(cols))

def add_col(sql: str) -> None:
    try:
        cur.execute(sql)
        conn.commit()
        print("Added:", sql)
    except sqlite3.OperationalError as e:
        print("Skip:", sql, "|", e)

if "values_json" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN values_json TEXT NOT NULL DEFAULT '[]'")
if "goals_json" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN goals_json TEXT NOT NULL DEFAULT '[]'")
if "constraints_json" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN constraints_json TEXT NOT NULL DEFAULT '[]'")
if "risk_tolerance" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN risk_tolerance REAL NOT NULL DEFAULT 0.5")
if "metadata_json" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
if "updated_at_epoch" not in cols:
    add_col("ALTER TABLE identity_profiles ADD COLUMN updated_at_epoch INTEGER NOT NULL DEFAULT 0")

now = int(time.time())
cur.execute(
    "UPDATE identity_profiles SET updated_at_epoch=? WHERE updated_at_epoch IS NULL OR updated_at_epoch=0",
    (now,),
)
conn.commit()

cur.execute("""
CREATE TABLE IF NOT EXISTS identity_alignment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    text TEXT NOT NULL,
    candidate_action TEXT,
    score REAL NOT NULL,
    components_json TEXT NOT NULL DEFAULT '{}',
    matched_json TEXT NOT NULL DEFAULT '{}',
    trace_json TEXT NOT NULL DEFAULT '{}',
    created_at_epoch INTEGER NOT NULL
)
""")
conn.commit()

print("Migration complete.")
conn.close()

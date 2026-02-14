import sqlite3
from pathlib import Path
import time

db_path = Path("app") / "ai_os_memory.db"
print(f"Using DB: {db_path}")

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1) Ensure table exists (new shape)
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

# 2) Add missing columns to old table
cols = [r["name"] for r in cur.execute("PRAGMA table_info(identity_profiles)").fetchall()]
print("Before columns:", cols)

def add_col(sql: str):
    try:
        cur.execute(sql)
        conn.commit()
        print("Added:", sql)
    except sqlite3.OperationalError as e:
        print("Skip:", e)

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

# 3) Backfill from legacy columns if they exist
cols2 = [r["name"] for r in cur.execute("PRAGMA table_info(identity_profiles)").fetchall()]
legacy_cols = set(cols2)

if "long_term_value_model_json" in legacy_cols:
    cur.execute("""
        UPDATE identity_profiles
        SET values_json = CASE
            WHEN values_json IS NULL OR values_json = '' OR values_json = '[]'
            THEN COALESCE(long_term_value_model_json, '[]')
            ELSE values_json
        END
    """)
if "stated_goals_json" in legacy_cols:
    cur.execute("""
        UPDATE identity_profiles
        SET goals_json = CASE
            WHEN goals_json IS NULL OR goals_json = '' OR goals_json = '[]'
            THEN COALESCE(stated_goals_json, '[]')
            ELSE goals_json
        END
    """)
if "behavioral_patterns_json" in legacy_cols:
    cur.execute("""
        UPDATE identity_profiles
        SET metadata_json = CASE
            WHEN metadata_json IS NULL OR metadata_json = '' OR metadata_json = '{}'
            THEN COALESCE(behavioral_patterns_json, '{}')
            ELSE metadata_json
        END
    """)

# updated_at_epoch backfill
now_epoch = int(time.time())
if "updated_at" in legacy_cols:
    cur.execute("""
        UPDATE identity_profiles
        SET updated_at_epoch = CASE
            WHEN updated_at_epoch IS NULL OR updated_at_epoch = 0
                THEN CASE
                    WHEN updated_at IS NULL OR updated_at = ''
                        THEN ?
                    ELSE CAST(strftime('%s', updated_at) AS INTEGER)
                END
            ELSE updated_at_epoch
        END
    """, (now_epoch,))
else:
    cur.execute("""
        UPDATE identity_profiles
        SET updated_at_epoch = ?
        WHERE updated_at_epoch IS NULL OR updated_at_epoch = 0
    """, (now_epoch,))

conn.commit()

# 4) Ensure events table exists
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

final_cols = [r["name"] for r in cur.execute("PRAGMA table_info(identity_profiles)").fetchall()]
print("After columns:", final_cols)
print("Migration complete.")
conn.close()

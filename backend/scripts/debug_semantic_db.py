import sqlite3

db = r"app\ai_os_memory.db"
c = sqlite3.connect(db)
cur = c.cursor()

print("=== BASIC COUNTS ===")
print("memories =", cur.execute("select count(*) from memories").fetchone()[0])

try:
    semantic_count = cur.execute("select count(*) from memories where memory_type='semantic'").fetchone()[0]
    print("semantic =", semantic_count)
except Exception as e:
    print("semantic count error:", e)

print("\n=== LATEST MEMORIES ===")
try:
    rows = cur.execute("select id, memory_type, substr(content,1,80) from memories order by id desc limit 15").fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print("latest memories error:", e)

print("\n=== TABLES ===")
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name").fetchall()]
print(tables)

print("\n=== EMBEDDING TABLE COUNTS ===")
for t in ["memory_embeddings", "embeddings", "vector_store_items", "vectors"]:
    if t in tables:
        try:
            cnt = cur.execute(f"select count(*) from {t}").fetchone()[0]
            print(f"{t} = {cnt}")
        except Exception as e:
            print(f"{t} count error:", e)

c.close()

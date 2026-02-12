import sqlite3

DB_PATH = "places_cache.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("📂 Tables:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

print("\n📊 Feedback Data:")
cursor.execute("SELECT place_name, vibe, user_rating FROM feedback;")
print(cursor.fetchall())

print("\n💙 Wishlist Data:")
cursor.execute("SELECT * FROM wishlist;")
print(cursor.fetchall())

print("\n🧠 Average Ratings:")
cursor.execute("""
SELECT place_name, AVG(user_rating)
FROM feedback
GROUP BY place_name;
""")
print(cursor.fetchall())

print("\n🔍 Integrity Check:")
cursor.execute("PRAGMA integrity_check;")
print(cursor.fetchone())

conn.close()
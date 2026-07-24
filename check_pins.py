import sqlite3
import datetime

conn = sqlite3.connect('database/pinterest_ai_agent.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM products")
total = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM products WHERE date(created_at) = date('now')")
today = cursor.fetchone()[0]

print(f"TOTAL_PINS:{total}")
print(f"TODAY_PINS:{today}")

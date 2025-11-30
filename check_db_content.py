import sqlite3
from pathlib import Path

db_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/temp_library.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"{'Filename':<40} | {'Content Length':<15} | {'Checksum'}")
print("-" * 80)

cursor.execute("SELECT filename, length(content), checksum FROM documents")
for row in cursor.fetchall():
    filename = row[0]
    length = row[1] if row[1] is not None else 0
    checksum = row[2]
    print(f"{filename:<40} | {length:<15} | {checksum}")

conn.close()

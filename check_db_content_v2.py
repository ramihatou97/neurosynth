import sqlite3
from pathlib import Path

db_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/temp_library.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"{'Filename':<40} | {'Content Length':<15}")
print("-" * 60)

# Check schema of pdf_text_cache first to be sure of column names
cursor.execute("PRAGMA table_info(pdf_text_cache)")
columns = [col[1] for col in cursor.fetchall()]
# Assuming columns likely include 'file_path' or 'filename' and 'content' or 'text'

if 'file_path' in columns and 'content' in columns:
    cursor.execute("SELECT file_path, length(content) FROM pdf_text_cache")
    for row in cursor.fetchall():
        path = Path(row[0]).name
        length = row[1] if row[1] is not None else 0
        print(f"{path:<40} | {length:<15}")
else:
    print(f"Columns in pdf_text_cache: {columns}")

conn.close()

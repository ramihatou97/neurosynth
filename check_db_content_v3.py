import sqlite3
from pathlib import Path

db_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/temp_library.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"{'Filename':<40} | {'Total Content Length':<20} | {'Page Count'}")
print("-" * 80)

cursor.execute(
    """
    SELECT pdf_path, sum(length(text_content)), count(page_number) 
    FROM pdf_text_cache 
    GROUP BY pdf_path
"""
)

for row in cursor.fetchall():
    path = Path(row[0]).name
    length = row[1] if row[1] is not None else 0
    pages = row[2]
    print(f"{path:<40} | {length:<20} | {pages}")

conn.close()

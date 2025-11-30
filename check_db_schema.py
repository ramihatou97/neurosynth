import sqlite3
from pathlib import Path

db_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/temp_library.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cursor.fetchall())

conn.close()

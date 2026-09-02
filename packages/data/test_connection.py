import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# load .env from repo root regardless of where this script is run from
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("select table_name from information_schema.tables where table_schema = 'public' order by table_name;")
tables = cur.fetchall()

print(f"Connected. Found {len(tables)} tables:")
for t in tables:
    print(" -", t[0])

cur.close()
conn.close()
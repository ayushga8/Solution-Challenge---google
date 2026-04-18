import psycopg2
import sys

dsn = "postgresql://postgres:KeWB%23q!y8-ZsE%2Ff@db.xhwlggizjayhqodxmbce.supabase.co:5432/postgres"

try:
    conn = psycopg2.connect(dsn)
    print("Connection successful!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")

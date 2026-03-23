import MySQLdb
import os
from dotenv import load_dotenv

load_dotenv()

try:
    db = MySQLdb.connect(
        host="localhost",
        user="root",
        passwd="",
        db="smile_well"
    )
    cur = db.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    print("Tables in smile_well:")
    for t in tables:
        print(t[0])
    
    cur.execute("DESCRIBE users")
    columns = cur.fetchall()
    print("\nColumns in users table:")
    for c in columns:
        print(f"{c[0]} ({c[1]})")
    
    db.close()
except Exception as e:
    print(f"Error: {e}")

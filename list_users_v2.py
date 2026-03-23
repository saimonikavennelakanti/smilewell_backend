import MySQLdb
import sys

# Set stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

try:
    db = MySQLdb.connect(
        host="localhost",
        user="root",
        passwd="",
        db="smile_well"
    )
    cur = db.cursor()
    cur.execute("SELECT id, full_name, email, password, is_verified FROM users")
    users = cur.fetchall()
    print("Users in database:")
    for u in users:
        print(f"ID: {u[0]}, Name: {u[1]}, Email: {u[2]}, Password: {u[3]}, Verified: {u[4]}")
    
    db.close()
except Exception as e:
    print(f"Error: {e}")

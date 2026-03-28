import MySQLdb

try:
    conn = MySQLdb.connect(host="localhost", user="root", password="", database="smile_well")
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE users ADD COLUMN fcm_token VARCHAR(255) DEFAULT NULL")
    conn.commit()
    print("Added fcm_token column.")
except Exception as e:
    if "Duplicate column name" in str(e): print("fcm_token already exists.")
    else: print("Error:", e)
finally:
    if 'cursor' in locals(): cursor.close()
    if 'conn' in locals(): conn.close()

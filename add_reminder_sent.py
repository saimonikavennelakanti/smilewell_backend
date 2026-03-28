import MySQLdb

try:
    conn = MySQLdb.connect(
        host="localhost",
        user="root",
        password="",
        database="smile_well"
    )
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE clinic_visits ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE")
    conn.commit()
    print("Added reminder_sent column successfully.")
except Exception as e:
    if "Duplicate column name" in str(e):
        print("reminder_sent already exists.")
    else:
        print("Error:", e)
finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()

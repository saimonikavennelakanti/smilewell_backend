import MySQLdb
import os
from dotenv import load_dotenv

load_dotenv()

def update_schema():
    try:
        db = MySQLdb.connect(
            host="localhost",
            user="root",
            passwd="",
            db="smile_well"
        )
        cursor = db.cursor()
        
        # Add notified column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE clinic_visits ADD COLUMN notified TINYINT(1) DEFAULT 0")
            print("Successfully added 'notified' column to clinic_visits.")
        except MySQLdb.OperationalError as e:
            if "Duplicate column name" in str(e):
                print("'notified' column already exists.")
            else:
                print(f"Error adding column: {e}")
        
        db.commit()
        db.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    update_schema()

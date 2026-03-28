import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def update_schema():
    try:
        # Try common MySQL connection parameters
        config = {
            'user': 'root',
            'password': '',
            'host': '127.0.0.1',
            'database': 'smile_well',
            'raise_on_errors': True
        }
        
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        
        # Add notified column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE clinic_visits ADD COLUMN notified TINYINT(1) DEFAULT 0")
            print("Successfully added 'notified' column to clinic_visits.")
        except mysql.connector.Error as e:
            if e.errno == 1060: # Duplicate column name
                print("'notified' column already exists.")
            else:
                print(f"Error adding column: {e}")
        
        cnx.commit()
        cursor.close()
        cnx.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    update_schema()

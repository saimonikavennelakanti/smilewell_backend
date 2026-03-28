import MySQLdb
import requests
from datetime import datetime, timedelta

def verify_auto_deletion():
    print("Verifying Auto-Deletion Logic...")
    
    try:
        db = MySQLdb.connect(
            host="localhost",
            user="root",
            passwd="",
            db="smile_well"
        )
        cursor = db.cursor()
        
        # 1. Insert an expired medication (End date was yesterday)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%d-%m-%Y')
        cursor.execute("""
            INSERT INTO medications (user_id, medication_name, dosage, frequency, time, start_date, end_date)
            VALUES (1, 'Expired Med', '10mg', 'Once a day', '08:00 AM', %s, %s)
        """, (yesterday, yesterday))
        med_id = cursor.lastrowid
        
        # 2. Insert an expired clinic visit (Date was yesterday)
        cursor.execute("""
            INSERT INTO clinic_visits (user_id, doctor_name, clinic_hospital, date, time, status)
            VALUES (1, 'Old Doctor', 'Past Clinic', %s, '09:00 AM', 'pending')
        """, (yesterday,))
        visit_id = cursor.lastrowid
        
        db.commit()
        print(f"Inserted Test Records: Med ID {med_id}, Visit ID {visit_id} (Date: {yesterday})")
        
        # 3. Trigger the manual check via API
        print("Triggering auto-deletion check...")
        response = requests.post("http://localhost:5000/check-and-notify")
        print(f"API Response: {response.status_code}")
        
        # 4. Check if they still exist
        cursor.execute("SELECT id FROM medications WHERE id = %s", (med_id,))
        if cursor.fetchone():
            print("❌ FAILED: Expired medication still exists")
        else:
            print("✅ SUCCESS: Expired medication deleted")
            
        cursor.execute("SELECT id FROM clinic_visits WHERE id = %s", (visit_id,))
        if cursor.fetchone():
            print("❌ FAILED: Expired clinic visit still exists")
        else:
            print("✅ SUCCESS: Expired clinic visit deleted")
            
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_auto_deletion()

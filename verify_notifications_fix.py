import MySQLdb
from datetime import datetime, timedelta

def verify_notifications():
    print("Verifying Notification Cleanup and Daily Tasks...")
    
    try:
        db = MySQLdb.connect(
            host="localhost",
            user="root",
            passwd="",
            db="smile_well"
        )
        cursor = db.cursor()
        
        # 1. Insert an old notification (from yesterday)
        yesterday = datetime.now() - timedelta(days=1)
        cursor.execute("""
            INSERT INTO user_notifications (user_id, title, message, type, created_at)
            VALUES (1, 'Old Notif', 'Should be deleted', 'general', %s)
        """, (yesterday,))
        old_id = cursor.lastrowid
        
        db.commit()
        print(f"Inserted Old Notification: ID {old_id} (Date: {yesterday})")
        
        # 2. Trigger the check via app.py's internal function logic
        # We can't easily call the internal function, but we can call the /check-and-notify endpoint
        import requests
        print("Triggering notification check via API...")
        response = requests.post("http://localhost:5000/check-and-notify")
        print(f"API Response: {response.status_code}")
        
        # 3. Check if old notification is deleted
        cursor.execute("SELECT id FROM user_notifications WHERE id = %s", (old_id,))
        if cursor.fetchone():
            print("❌ FAILED: Old notification still exists")
        else:
            print("✅ SUCCESS: Old notification deleted")
            
        # 4. Check if "Daily Tasks" was created for today
        cursor.execute("""
            SELECT id FROM user_notifications 
            WHERE user_id = 1 AND title = 'Daily Tasks' AND DATE(created_at) = CURDATE()
        """)
        if cursor.fetchone():
            print("✅ SUCCESS: Daily Tasks notification created for today")
        else:
            print("❌ FAILED: Daily Tasks notification NOT created")
            
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_notifications()

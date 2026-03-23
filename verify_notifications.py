from datetime import datetime, timedelta
import requests
import json

BASE_URL = 'http://127.0.0.1:5000'
USER_ID = 1 # Assuming user 1 exists

def verify_reminders():
    now = datetime.now()
    target_time = (now + timedelta(minutes=10)).strftime('%I:%M %p')
    today_str = now.strftime('%m/%d/%Y')
    
    print(f"Testing for target time: {target_time} on {today_str}")

    # 1. Add a medication due in 10 mins
    med_data = {
        "user_id": USER_ID,
        "medication_name": "Test Med 10m",
        "dosage": "1 pill",
        "frequency": "Daily",
        "time": target_time,
        "start_date": today_str,
        "end_date": today_str,
        "instructions": "Take with water"
    }
    
    print("Adding test medication...")
    resp = requests.post(f"{BASE_URL}/add-medication", json=med_data)
    print(f"Add Med Resp: {resp.status_code} - {resp.text}")

    # 2. Add a clinic visit due in 10 mins
    visit_data = {
        "user_id": USER_ID,
        "doctor_name": "Dr. Verification",
        "clinic_hospital": "Test Clinic",
        "date": today_str,
        "time": target_time,
        "notes": "Verify 10m reminder"
    }
    
    print("Adding test clinic visit...")
    resp = requests.post(f"{BASE_URL}/add-clinic-visit", json=visit_data)
    print(f"Add Visit Resp: {resp.status_code} - {resp.text}")

    # 3. Trigger check-and-notify
    print("Triggering check-and-notify...")
    resp = requests.post(f"{BASE_URL}/check-and-notify", json={"user_id": USER_ID})
    print(f"Check Notify Resp: {resp.status_code} - {resp.text}")

    # 4. Fetch notifications to verify entry
    print("Fetching notifications...")
    resp = requests.get(f"{BASE_URL}/get-notifications/{USER_ID}")
    if resp.status_code == 200:
        notifs = resp.json()
        print(f"Found {len(notifs)} notifications.")
        for n in notifs[:5]: # Show latest 5
            print(f"- {n['title']}: {n['message']} ({n['created_at']})")
    else:
        print(f"Error fetching notifications: {resp.status_code}")

if __name__ == "__main__":
    verify_reminders()

import requests
from datetime import datetime, timedelta
import time

BASE_URL = "http://127.0.0.1:5000"
USER_ID = 36 # Valid user in database

def test_automated_notification():
    now = datetime.now()
    # Schedule a visit 1 minute from now
    scheduled_time_dt = now + timedelta(minutes=1)
    scheduled_time_str = scheduled_time_dt.strftime("%I:%M %p")
    scheduled_date_str = scheduled_time_dt.strftime("%m/%d/%Y")

    print(f"Current Time: {now.strftime('%I:%M:%S %p')}")
    print(f"Scheduling visit for: {scheduled_time_str} on {scheduled_date_str}")

    # Add the clinic visit
    visit_data = {
        "user_id": USER_ID,
        "doctor_name": "Dr. Scheduler Test",
        "clinic_hospital": "Automation Lab",
        "date": scheduled_date_str,
        "time": scheduled_time_str,
        "notes": "Testing automated email notification"
    }

    try:
        resp = requests.post(f"{BASE_URL}/add-clinic-visit", json=visit_data)
        if resp.status_code == 201:
            print("Visit added successfully.")
        else:
            print(f"Failed to add visit: {resp.text}")
            return

        print("Waiting for the scheduler to trigger (checking every minute)...")
        # Wait up to 3 minutes to see if notification is triggered
        found = False
        for i in range(180):
            time.sleep(1)
            if i % 30 == 0:
                print(f"Checking for notification... {i}s elapsed")
            
            # Check notifications endpoint
            notif_resp = requests.get(f"{BASE_URL}/get-notifications/{USER_ID}")
            if notif_resp.status_code == 200:
                notifs = notif_resp.json()
                for n in notifs:
                    if "Visit Starting" in n['title'] and "Dr. Scheduler Test" in n['message']:
                        print(f"SUCCESS! Notification found: {n['message']}")
                        found = True
                        break
            if found: break
        
        if not found:
            print("FAILURE: Notification not triggered within 3 minutes.")

    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_automated_notification()

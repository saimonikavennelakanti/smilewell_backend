import requests
from datetime import datetime, timedelta
import time

BASE_URL = 'http://127.0.0.1:5000'
USER_ID = 1 # Assuming user 1 exists

def test_add_medication_with_frequency():
    print("Testing Add Medication with 'Every 6 hours' frequency...")
    today = datetime.now()
    start_date = today.strftime('%m/%d/%Y')
    end_date = (today + timedelta(days=7)).strftime('%m/%d/%Y')
    # Use a time string that matches the format expected by the backend
    time_str = today.strftime('%I:%M %p')
    
    payload = {
        "user_id": USER_ID,
        "medication_name": "Test Med 6H",
        "dosage": "500mg",
        "frequency": "Every 6 hours",
        "time": time_str,
        "start_date": start_date,
        "end_date": end_date,
        "instructions": "Take with water"
    }
    
    response = requests.post(f"{BASE_URL}/add-medication", json=payload)
    if response.status_code == 201:
        print("✅ SUCCESS: Medication added successfully (Fixed the 500 error!)")
    else:
        print(f"❌ FAILED: Status code {response.status_code}, Body: {response.text}")

def test_check_and_notify():
    print("\nTesting 'check-and-notify' logic...")
    response = requests.post(f"{BASE_URL}/check-and-notify", json={"user_id": USER_ID})
    if response.status_code == 200:
        print("✅ SUCCESS: check-and-notify called successfully")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ FAILED: Status code {response.status_code}, Body: {response.text}")

if __name__ == "__main__":
    # Note: This script requires the backend to be running.
    # It also relies on a user with ID 1 existing in the DB.
    try:
        test_add_medication_with_frequency()
        test_check_and_notify()
    except Exception as e:
        print(f"Error running test: {e}")

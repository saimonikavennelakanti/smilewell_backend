import requests
from datetime import datetime, timedelta

BASE_URL = 'http://127.0.0.1:5000'
USER_ID = 1  # Using 1 since DB is fresh or user will exist

def add_mock_medication(name, start_date, end_date):
    response = requests.post(f"{BASE_URL}/add-medication", json={
        "user_id": USER_ID,
        "medication_name": name,
        "start_date": start_date,
        "end_date": end_date
    })
    print(f"Added {name}: {response.json()}")
    return response.status_code == 201

def test_medications():
    today = datetime.now()
    yesterday = (today - timedelta(days=1)).strftime('%m/%d/%Y')
    tomorrow = (today + timedelta(days=1)).strftime('%m/%d/%Y')
    today_str = today.strftime('%m/%d/%Y')

    print("Adding Mock Medications:")
    add_mock_medication("Past Medication", "01/01/2026", yesterday)
    add_mock_medication("Future Medication", tomorrow, "12/12/2026")
    add_mock_medication("Active Medication", yesterday, tomorrow)

    print("\nFetching Medications:")
    response = requests.get(f"{BASE_URL}/get-medications/{USER_ID}")
    
    if response.status_code == 200:
        medications = response.json()
        names = [m['medication_name'] for m in medications]
        print(f"Returned Medications: {names}")

        # Assertions
        if "Past Medication" in names:
            print("❌ FAILED: Past Medication should NOT be returned.")
        elif "Future Medication" in names:
            print("❌ FAILED: Future Medication should NOT be returned.")
        elif "Active Medication" not in names:
            print("❌ FAILED: Active Medication SHOULD be returned.")
        else:
            print("✅ SUCCESS: Only the Active Medication was returned.")
    else:
        print(f"Error fetching: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_medications()

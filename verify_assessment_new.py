import requests
import json

BASE_URL = "http://localhost:5000"

def test_new_scoring():
    print("Testing New Assessment Scoring...")
    
    # Payload similar to Android and Web
    payload = {
        "user_id": 1,
        "date": "2026-03-27",
        "time": "09:00:00",
        "answers": [
            {"question_id": 1, "choice": "Never"},       # 20
            {"question_id": 2, "choice": "Hardly ever"},  # 16
            {"question_id": 3, "choice": "Occasionally"}, # 12
            {"question_id": 4, "choice": "Fairly often"}, # 8
            {"question_id": 5, "choice": "Often"},        # 4
            # Oral Total: 20+16+12+8+4 = 60
            
            {"question_id": 6, "choice": "Never"},       # 20
            {"question_id": 7, "choice": "Never"},       # 20
            {"question_id": 8, "choice": "Never"},       # 20
            {"question_id": 9, "choice": "Never"},       # 20
            {"question_id": 10, "choice": "Never"}       # 20
            # Mental Total: 100
        ]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/submit-assessment", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            print(f"Oral Score: {data.get('oral_score')}% (Expected 60%)")
            print(f"Mental Score: {data.get('mental_score')}% (Expected 100%)")
            if data.get('oral_score') == 60 and data.get('mental_score') == 100:
                print("✅ PASSED")
            else:
                print("❌ FAILED: Wrong scores")
        else:
            print(f"❌ FAILED: Error response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_new_scoring()

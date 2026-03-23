import requests
import mysql.connector
from datetime import datetime

BASE_URL = 'http://127.0.0.1:5000'
USER_ID = 1

def test_assessment_submission_and_storage():
    print("Testing Assessment Submission and Detailed Storage...")
    
    # 1. Submit Assessment
    answers = [{"question_id": i, "choice": "Yes" if i % 2 == 0 else "No"} for i in range(1, 11)]
    payload = {
        "user_id": USER_ID,
        "answers": answers,
        "date": datetime.now().strftime('%Y-%m-%d'),
        "time": datetime.now().strftime('%H:%M:%S')
    }
    
    response = requests.post(f"{BASE_URL}/submit-assessment", json=payload)
    if response.status_code != 201:
        print(f"❌ FAILED: Submission failed with status {response.status_code}")
        return

    data = response.json()
    result_id = data.get('result_id')
    print(f"✅ SUCCESS: Assessment submitted. Result ID: {result_id}")

    # 2. Verify Database (Using mysql-connector-python as a separate check)
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smile_well"
        )
        cursor = db.cursor()
        
        # Check daily_results
        cursor.execute("SELECT oral_score, mental_score FROM daily_results WHERE id = %s", (result_id,))
        result = cursor.fetchone()
        if result:
            print(f"✅ SUCCESS: Row found in daily_results. Scores: Oral={result[0]}, Mental={result[1]}")
        else:
            print("❌ FAILED: Row not found in daily_results")

        # Check assessment_answers
        cursor.execute("SELECT COUNT(*) FROM assessment_answers WHERE result_id = %s", (result_id,))
        count = cursor.fetchone()[0]
        if count == 10:
            print(f"✅ SUCCESS: 10 rows found in assessment_answers for result_id {result_id}")
        else:
            print(f"❌ FAILED: Expected 10 rows in assessment_answers, found {count}")
            
        cursor.close()
        db.close()
    except Exception as e:
        print(f"⚠️ Could not verify DB directly (maybe mysql-connector not installed): {e}")
        print("Please verify the 'assessment_answers' table manually in your DB client.")

if __name__ == "__main__":
    test_assessment_submission_and_storage()
 toxicology_report = """
 # Verification Plan
 1. Run backend.
 2. Run this script.
 """

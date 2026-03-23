import requests
import json
import os

def test_dental_screening():
    url = 'http://localhost:5000/upload-photo'
    
    # Check if a sample image exists, if not, we'll just skip the actual upload part
    # or assume the server is running and can handle a dummy request.
    # For a real test, we'd need a valid path to an image.
    sample_image_path = 'c:/Users/royal/AndroidStudioProjects/smilewell/smilewell_backend/uploads/scans/test_sample.jpg'
    
    if not os.path.exists(sample_image_path):
        print(f"Sample image not found at {sample_image_path}. Please provide a real image for full testing.")
        return

    files = {'file': open(sample_image_path, 'rb')}
    
    try:
        response = requests.post(url, files=files)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Analysis Result:")
            print(json.dumps(result, indent=2))
            
            analysis = result.get('analysis', {})
            required_keys = ["status", "problem_detected", "severity", "confidence_percentage", "risk_level", "recommendation", "visit_dentist", "note"]
            
            missing_keys = [key for key in required_keys if key not in analysis]
            if not missing_keys:
                print("SUCCESS: AI returned all required JSON keys.")
            else:
                print(f"FAILURE: AI response is missing keys: {missing_keys}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == '__main__':
    # Note: Flask server must be running on localhost:5000
    print("Starting Dental Screening AI Test...")
    test_dental_screening()

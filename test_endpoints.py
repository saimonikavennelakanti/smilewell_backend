import requests
import json

BASE_URL = "http://localhost:5000"

def test_register():
    url = f"{BASE_URL}/register"
    data = {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "password123"
    }
    try:
        response = requests.post(url, json=data)
        print(f"Register Status: {response.status_code}")
        print(f"Register Response: {response.text}")
    except Exception as e:
        print(f"Register Error: {e}")

def test_resend_otp():
    url = f"{BASE_URL}/resend-otp"
    data = {"email": "test@example.com"}
    try:
        response = requests.post(url, json=data)
        print(f"Resend Status: {response.status_code}")
        print(f"Resend Response: {response.text}")
    except Exception as e:
        print(f"Resend Error: {e}")

if __name__ == "__main__":
    test_register()
    test_resend_otp()

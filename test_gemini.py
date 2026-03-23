from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def test_voice():
    print("Testing Voice Assistant...")
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Hello, can you help me with my dental care?")
    print(f"Response: {response.text}\n")

if __name__ == "__main__":
    test_voice()

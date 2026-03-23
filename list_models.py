import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    models = genai.list_models()
    for m in models:
        try:
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
        except:
            pass
except Exception as e:
    print(f"Error listing models: {e}")

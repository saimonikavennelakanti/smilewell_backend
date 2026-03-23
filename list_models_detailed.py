import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print(f"Listing models for key: {os.getenv('GEMINI_API_KEY')[:10]}...")
    for m in genai.list_models():
        print(f"Name: {m.name}, Display Name: {m.display_name}, Methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error: {e}")

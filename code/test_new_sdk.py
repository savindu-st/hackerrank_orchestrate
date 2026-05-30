import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='Hello, who are you?'
    )
    print("Response successful!")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")

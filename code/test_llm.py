import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
model_name = os.getenv("MODEL_NAME", "gemini-1.5-pro")

print(f"Testing model: {model_name}")
print(f"API Key starts with: {api_key[:10] if api_key else 'None'}")

llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

try:
    response = llm.invoke("Hello, who are you?")
    print("Response successful!")
    print(response.content)
except Exception as e:
    print(f"Error: {e}")

import os
from dotenv import load_dotenv
from google import genai

try:
    from retrive import retrieve_documents
except ImportError:
    from app.retrive import retrieve_documents
    
from pathlib import Path
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")
if not MODEL_NAME:
    raise ValueError("GEMINI_MODEL not found in .env file.")

client = genai.Client(api_key=API_KEY)
def build_prompt(question, context):
    prompt = f"""
You are a helpful research assistant.

Answer the user's question using the information
provided in the context below.

If the answer cannot be found in the context, say:
"I could not find the answer in the retrieved documents."

Context:
{context}

Question:
{question}

Answer:
"""
    return prompt

def main():

    question = input("Enter your question: ")
    results, relevant_results, context, retrieval_time = (
        retrieve_documents(question, k=5)
    )
    if not context:
        print("No relevant information found.")
        return
    prompt = build_prompt(question, context)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    print("\n" + response.text)

if __name__ == "__main__":
    main()
import os
from dotenv import load_dotenv
from google import genai
from retrive import retrieve_documents
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
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
        model="gemini-3.8-flash",
        contents=prompt
    )
    print("\n" + response.text)

if __name__ == "__main__":
    main()
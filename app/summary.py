import time
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

CUR_DIR = Path(__file__).resolve().parent

VECTOR_DB = CUR_DIR / "vector_db"
HISTORICAL_VECTOR_DB = CUR_DIR / "historical_vector_db"


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found in .env file."
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)



embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

recent_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(VECTOR_DB)
)
historical_store = Chroma(
    collection_name="historical_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(HISTORICAL_VECTOR_DB)
)


NEWS_CATEGORIES = {

    "NATIONAL NEWS":
        "important national news and major developments in India",

    "STATE / DISTRICT NEWS":
        "important state-level and district-level news and local developments in India",

    "SPORTS":
        "important sports news, matches, tournaments, players and sporting events",

    "FINANCIAL / BUSINESS NEWS":
        "important financial, economic, stock market, business and corporate news",

    "POLITICAL NEWS":
        "important political news, government decisions, elections, political parties and politicians"
}


def retrieve_category_news(store, category_query, k=5):
    return store.similarity_search(category_query, k=k)


def remove_duplicates(documents):

    unique_documents = []

    seen = set()


    for document in documents:

        content = document.page_content.strip()
        metadata = document.metadata
        chunk_id = metadata.get(
            "chunk_id"
        )
        paper_id = metadata.get(
            "paper_id"
        )


        if chunk_id:

            key = chunk_id

        elif paper_id:

            key = (
                paper_id,
                content
            )
        else:
            key = content


        if key in seen:
            continue


        seen.add(key)

        unique_documents.append(
            document
        )


    return unique_documents


def build_context(recent_category_documents, historical_category_documents):
    context_parts = []
    groups = (
        ("RECENT NEWS (downloaded within the last 24 hours)", recent_category_documents),
        ("HISTORICAL NEWS (downloaded more than 24 hours ago)", historical_category_documents),
    )
    for label, category_documents in groups:
        context_parts.append(f"\n\n================ {label} ================\n")
        for category, documents in category_documents.items():
            context_parts.append(f"\n--- {category} ---\n")
            for index, document in enumerate(documents, start=1):
                metadata = document.metadata
                context_parts.append(
                    f"\nNEWS CHUNK {index}\n"
                    f"Source: {metadata.get('source', 'Unknown')}\n"
                    f"Downloaded: {metadata.get('paper_retrieval_time', 'Unknown')}\n"
                    f"Paper ID: {metadata.get('paper_id', 'Unknown')}\n"
                    f"Content:\n{document.page_content}\n"
                )
    return "\n".join(context_parts)


def build_summary_prompt(context):

    prompt = f"""
You are a news summarization assistant.

Create a concise and informative summary of the news
contained in the retrieved context.

IMPORTANT RULES:

1. Use the information provided in the retrieved
   context.

2. Do NOT use only your own knowledge.

3. Do NOT introduce facts that are not present in the
   retrieved context.

4. Do NOT speculate.

5. If multiple chunks describe the same event, combine
   them into one news story.

6. Do not unnecessarily repeat the same story across
   categories.

7. Preserve important names, numbers, dates, locations,
   organizations and other factual details present in
   the source.

8. If there is no relevant news for a category, write:
   "No relevant news found in the retrieved context."

Organize the output into these sections, keeping recent and historical news separate:

## RECENT / HOT NEWS (LAST 24 HOURS)
Include subsections for NATIONAL NEWS, STATE / DISTRICT NEWS, SPORTS,
FINANCIAL / BUSINESS NEWS, and POLITICAL NEWS.

## HISTORICAL NEWS (OLDER THAN 24 HOURS)
Include subsections for NATIONAL NEWS, STATE / DISTRICT NEWS, SPORTS,
FINANCIAL / BUSINESS NEWS, and POLITICAL NEWS.

Clearly identify the download timestamp when available. Do not describe historical
news as breaking or current. If a section has no relevant results, say so.

For each important story:

- Give a short headline.
- Give a 2–4 sentence summary.
- Mention the source when available.

Finally provide:

## KEY TAKEAWAYS

Give 3–5 of the most important developments from
the retrieved news.

Remember:

The retrieved context is the ONLY source of truth.
If information is missing, do not fill the gap using
your own knowledge.

------------------------------------------------------------
RETRIEVED NEWS
------------------------------------------------------------

{context}

------------------------------------------------------------
END OF RETRIEVED NEWS
------------------------------------------------------------
"""
    return prompt

def generate_summary(context):
    prompt = build_summary_prompt(
        context
    )
    response = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )
    return response.output_text

def create_summary():
    print("\nRetrieving recent and historical news...\n")
    start_time = time.perf_counter()
    recent_category_documents = {}
    historical_category_documents = {}

    for category, query in NEWS_CATEGORIES.items():
        print(f"Retrieving recent: {category}")
        recent_category_documents[category] = retrieve_category_news(recent_store, query, k=5)
        print(f"Retrieving historical: {category}")
        historical_category_documents[category] = retrieve_category_news(historical_store, query, k=5)

    for category in NEWS_CATEGORIES:
        recent_category_documents[category] = remove_duplicates(recent_category_documents[category])
        historical_category_documents[category] = remove_duplicates(historical_category_documents[category])

    retrieval_time = time.perf_counter() - start_time
    total_chunks = sum(len(docs) for docs in recent_category_documents.values()) + sum(
        len(docs) for docs in historical_category_documents.values()
    )
    print(f"\nRetrieved {total_chunks} chunks across both databases.")
    print(f"Retrieval time: {retrieval_time * 1000:.2f} ms")
    context = build_context(recent_category_documents, historical_category_documents)
    print("\nGenerating news summary...")
    summary = generate_summary(context)
    print("\n" + "=" * 80)
    print("NEWS SUMMARY")
    print("=" * 80)
    print(summary)
    print("=" * 80)
    return summary

if __name__ == "__main__":

    create_summary()
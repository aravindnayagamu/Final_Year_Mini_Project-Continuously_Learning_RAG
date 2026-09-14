import time
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

CUR_DIR = Path(__file__).resolve().parent

VECTOR_DB = CUR_DIR / "vector_db"


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

vector_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(VECTOR_DB)
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


def retrieve_category_news(
    category_query,
    k=5
):

    documents = vector_store.similarity_search(
        category_query,
        k=k
    )

    return documents


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


def build_context(category_documents):

    context_parts = []


    for category, documents in category_documents.items():

        context_parts.append(
            f"\n\n##############################\n"
            f"{category}\n"
            f"##############################\n"
        )


        for index, document in enumerate(
            documents,
            start=1
        ):

            metadata = document.metadata

            source = metadata.get(
                "source",
                "Unknown"
            )

            paper_id = metadata.get(
                "paper_id",
                "Unknown"
            )

            chunk_id = metadata.get(
                "chunk_id",
                "Unknown"
            )


            context_parts.append(
                f"""
--- NEWS CHUNK {index} ---

Paper ID:
{paper_id}

Chunk ID:
{chunk_id}

Source:
{source}

Content:
{document.page_content}

"""
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

Organize the output into exactly these five sections:

## NATIONAL NEWS

Important national-level developments.

## STATE / DISTRICT NEWS

Important state-level and district-level developments.

## SPORTS

Important sports developments.

## FINANCIAL / BUSINESS NEWS

Important financial, economic and business developments.

## POLITICAL NEWS

Important political developments.

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
    print("\nRetrieving news...\n")
    start_time = time.perf_counter()
    category_documents = {}
    for category, query in NEWS_CATEGORIES.items():
        print(
            f"Retrieving: {category}"
        )
        documents = retrieve_category_news(
            query,
            k=5
        )
        category_documents[category] = documents
    for category in category_documents:

        category_documents[category] = (
            remove_duplicates(
                category_documents[category]
            )
        )
    end_time = time.perf_counter()
    retrieval_time = (
        end_time - start_time
    )    
    total_chunks = sum(
        len(documents)
        for documents
        in category_documents.values()
    )
    print(
        f"\nRetrieved {total_chunks} unique chunks."
    )
    print(
        f"Retrieval time: "
        f"{retrieval_time * 1000:.2f} ms"
    )
    context = build_context(
        category_documents
    )
    print(
        "\nGenerating news summary..."
    )
    summary = generate_summary(
        context
    )
    print(
        "\n"
        + "=" * 80
    )
    print(
        "NEWS SUMMARY"
    )
    print(
        "=" * 80
    )
    print(summary)
    print(
        "=" * 80
    )
    return summary

if __name__ == "__main__":

    create_summary()
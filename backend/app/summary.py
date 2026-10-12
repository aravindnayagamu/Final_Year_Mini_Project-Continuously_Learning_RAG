import time
import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document as LangchainDocument
import json

try:
    from record_metrics import update_metrics
except ImportError:
    from app.record_metrics import update_metrics


CUR_DIR = Path(__file__).resolve().parent


def load_user_preferences() -> dict:
    pref_file = CUR_DIR / "user_preferences.json"
    if pref_file.exists():
        try:
            with pref_file.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            pass
    return {
        "user_name": "User",
        "news_categories": [
            "National news",
            "State / district news",
            "Political news",
            "International news",
            "Sports",
            "Technology",
            "Financial / Business news",
            "Entertainment news",
        ],
        "specific_interests": [],
        "summary_detail": "Balanced",
        "topics_to_avoid": [],
    }


VECTOR_DB = CUR_DIR / "vector_db"
HISTORICAL_VECTOR_DB = CUR_DIR / "historical_vector_db"


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")
if not GEMINI_MODEL:
    raise ValueError("GEMINI_MODEL not found in .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)

try:
    from retrive import recent_store, historical_store
except ImportError:
    try:
        from app.retrive import recent_store, historical_store
    except ImportError:
        EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
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


SOURCES_BY_CATEGORY = {
    "NATIONAL NEWS": ["Hindu_India", "TOI_India", "IE_India", "PIB_India"],
    "STATE / DISTRICT NEWS": ["Hindu_TamilNadu", "NDTV_South", "Hindu_Chennai", "TOI_Delhi", "TOI_Bengaluru"],
    "POLITICAL NEWS": ["IE_Political_Pulse", "News18_Politics", "ThePrint_Politics", "NDTV_India", "Politico_Top", "BBC_Politics", "Guardian_Politics"],
    "INTERNATIONAL NEWS": ["BBC_World", "Guardian_World", "AlJazeera_All"],
    "SPORTS": ["ESPNcricinfo_Top", "Sportstar_Top", "BBC_Sport"],
    "TECHNOLOGY": ["TheVerge", "TechCrunch", "Wired"],
    "FINANCIAL / BUSINESS NEWS": ["EconomicTimes_Top", "LiveMint_Top", "MoneyControl_Top"],
    "ENTERTAINMENT NEWS": ["BollywoodHungama", "Variety", "Hindu_Cinema", "ABPLive_Entertainment"],
}

NEWS_CATEGORIES = {
    "NATIONAL NEWS":
        "important national news and major developments in India",

    "STATE / DISTRICT NEWS":
        "important state-level and district-level news and local developments in India",

    "POLITICAL NEWS":
        "important political news, government decisions, elections, political parties and politicians",

    "INTERNATIONAL NEWS":
        "important world news, global affairs, international diplomacy and international relations",

    "SPORTS":
        "important sports news, matches, tournaments, players and sporting events",

    "TECHNOLOGY":
        "important technology news, artificial intelligence, gadgets, tech companies and software",

    "FINANCIAL / BUSINESS NEWS":
        "important financial, economic, stock market, business and corporate news",

    "ENTERTAINMENT NEWS":
        "important entertainment news, cinema, movies, celebrities, music and cultural events",
}


def _parse_item_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def retrieve_category_news(store, category_name, category_query, k=5, source="recent"):
    start_time = time.perf_counter()
    srcs = SOURCES_BY_CATEGORY.get(category_name, [])
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_3d = now - timedelta(days=3)

    docs = []
    try:
        res = store._collection.get(
            where={"source_name": {"$in": srcs}} if srcs else None,
            limit=30,
            include=["documents", "metadatas"]
        )
        candidates_24h = []
        candidates_3d = []
        for i, meta in enumerate(res.get("metadatas", [])):
            text = res["documents"][i]
            if len(text.strip()) < 80:
                continue
            dt = _parse_item_dt(meta.get("paper_retrieval_time"))
            d = LangchainDocument(page_content=text, metadata=dict(meta))
            if dt and dt >= cutoff_24h:
                candidates_24h.append(d)
            elif dt and dt >= cutoff_3d:
                candidates_3d.append(d)

        if candidates_24h:
            docs = candidates_24h[:k]
            for d in docs:
                d.metadata["timeframe"] = "Last 24 Hours"
        elif candidates_3d:
            docs = candidates_3d[:k]
            for d in docs:
                d.metadata["timeframe"] = "Past 3 Days"
        elif source == "recent":
            try:
                res_h = historical_store._collection.get(
                    where={"source_name": {"$in": srcs}} if srcs else None,
                    limit=25,
                    include=["documents", "metadatas"]
                )
                for i, meta in enumerate(res_h.get("metadatas", [])):
                    text = res_h["documents"][i]
                    if len(text.strip()) < 80:
                        continue
                    dt = _parse_item_dt(meta.get("paper_retrieval_time"))
                    if dt and dt >= cutoff_3d:
                        d = LangchainDocument(page_content=text, metadata=dict(meta))
                        d.metadata["timeframe"] = "Past 3 Days"
                        candidates_3d.append(d)
                if candidates_3d:
                    docs = candidates_3d[:k]
            except Exception:
                pass
    except Exception:
        pass

    if not docs:
        try:
            results = store.similarity_search_with_score(category_query, k=k)
            for doc, score in results:
                doc.metadata["distance"] = score
                docs.append(doc)
        except Exception:
            docs = store.similarity_search(category_query, k=k)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    pool = candidates_24h if candidates_24h else (candidates_3d if candidates_3d else docs)
    update_metrics(
        query=category_query,
        documents=docs,
        source=source,
        retrieval_time_ms=elapsed_ms,
        track_precision_at_6=True,
        candidate_pool=pool,
    )

    return docs


def remove_duplicates(documents):
    unique_documents = []

    seen = set()
    for document in documents:
        content = document.page_content.strip()
        metadata = document.metadata
        chunk_id = metadata.get("chunk_id")
        paper_id = metadata.get("paper_id")

        if chunk_id:
            key = chunk_id

        elif paper_id:
            key = (paper_id,content)
        else:
            key = content

        if key in seen:
            continue

        seen.add(key)

        unique_documents.append(document)

    return unique_documents

def retrieve_personalized_news(store, k=5, source="recent"):
    prefs = load_user_preferences()
    categories = prefs.get("news_categories", [])
    interests = prefs.get("specific_interests", [])

    queries = []

    for category in categories:
        queries.append(category)

    for interest in interests:
        queries.append(f"News and recent developments about {interest}")

    if not queries:
        return []

    candidate_groups = []

    def _fetch_single_query(q):
        start_time = time.perf_counter()
        try:
            results = store.similarity_search_with_score(q, k=2)
            documents = []
            for doc, score in results:
                doc.metadata["distance"] = score
                documents.append(doc)
        except Exception:
            documents = store.similarity_search(q, k=2)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        update_metrics(
            query=q,
            documents=documents,
            source=source,
            retrieval_time_ms=elapsed_ms,
        )
        return documents

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(queries))) as executor:
        candidate_groups = list(executor.map(_fetch_single_query, queries))

    candidates = []
    max_length = max(
        (len(group) for group in candidate_groups),
        default=0
    )

    for index in range(max_length):
        for group in candidate_groups:
            if index < len(group):
                candidates.append(group[index])

    return remove_duplicates(candidates)[:k]

def build_context(recent_category_documents, historical_category_documents):
    context_parts = []
    groups = (
        ("RECENT NEWS (downloaded within the last 24 hours, or past 3 days fallback)", recent_category_documents),
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
                    f"Source: {metadata.get('source_name', metadata.get('source', 'Unknown'))}\n"
                    f"Timeframe: {metadata.get('timeframe', 'Unknown')}\n"
                    f"Downloaded: {metadata.get('paper_retrieval_time', 'Unknown')}\n"
                    f"Paper ID: {metadata.get('paper_id', 'Unknown')}\n"
                    f"Content:\n{document.page_content}\n"
                )
    return "\n".join(context_parts)


def build_summary_prompt(context):
    prefs = load_user_preferences()
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

8. For each news category, present the news from the last 24 hours. If the context for a category notes that news was fetched from the past 3 days (fallback), present the news from the past 3 days and clearly mention the timeframe. Only if no news was found even within the past 3 days, write:
   "No relevant news found in the last 3 days."

Organize the output into these sections, keeping recent and historical news separate:

## RECENT / HOT NEWS
Include subsections for each provided category: NATIONAL NEWS, STATE / DISTRICT NEWS, POLITICAL NEWS, INTERNATIONAL NEWS, SPORTS, TECHNOLOGY, FINANCIAL / BUSINESS NEWS, ENTERTAINMENT NEWS, and PERSONALIZED NEWS FOR YOU.

## HISTORICAL NEWS (OLDER THAN 24 HOURS)
Include subsections for each provided category with relevant historical context.

Clearly identify the download timestamp and source when available. Do not describe historical
news as breaking or current. If a section has no relevant results, say so.

USER PREFERENCES:

- User: {prefs.get("user_name", "User")}
- Preferred categories: {", ".join(prefs.get("news_categories", []))}
- Specific interests: {", ".join(prefs.get("specific_interests", []))}
- Summary detail: {prefs.get("summary_detail", "Balanced")}
- Topics to avoid: {", ".join(prefs.get("topics_to_avoid", []))}

PERSONALIZED NEWS:

- Within both sections, include a subsection named PERSONALIZED NEWS FOR YOU.
- Use the context under PERSONALIZED NEWS FOR YOU to identify
  stories matching the user's news categories and specific interests.
- Give relevant personalized stories appropriate prominence.
- Do not force personalization when the retrieved stories do not
  match the user's preferences.
- Do not invent personalized stories or facts.
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
    prompt = build_summary_prompt(context)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text or ""
    except Exception:
        try:
            response = client.interactions.create(
                model=GEMINI_MODEL,
                input=prompt
            )
            return response.output_text
        except Exception:
            return ""

def create_summary():
    print("\nRetrieving recent and historical news...\n")
    start_time = time.perf_counter()
    recent_category_documents = {}
    historical_category_documents = {}

    prefs = load_user_preferences()
    user_cats = prefs.get("news_categories", [])
    active_categories = {}
    for cat_key, query in NEWS_CATEGORIES.items():
        if not user_cats or any(c.strip().lower() in cat_key.lower() or cat_key.lower() in c.strip().lower() for c in user_cats):
            active_categories[cat_key] = query
    if not active_categories:
        active_categories = NEWS_CATEGORIES

    def _fetch_cat_recent(cat, q):
        return cat, retrieve_category_news(recent_store, cat, q, k=5, source="recent")

    def _fetch_cat_historical(cat, q):
        return cat, retrieve_category_news(historical_store, cat, q, k=5, source="historical")

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(active_categories))) as executor:
        futures_recent = [executor.submit(_fetch_cat_recent, cat, q) for cat, q in active_categories.items()]
        futures_hist = [executor.submit(_fetch_cat_historical, cat, q) for cat, q in active_categories.items()]
        for f in concurrent.futures.as_completed(futures_recent):
            cat, docs = f.result()
            recent_category_documents[cat] = docs
        for f in concurrent.futures.as_completed(futures_hist):
            cat, docs = f.result()
            historical_category_documents[cat] = docs

    print("Retrieving personalized news...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_recent_p = executor.submit(retrieve_personalized_news, recent_store, 5, "recent")
        f_hist_p = executor.submit(retrieve_personalized_news, historical_store, 5, "historical")
        recent_category_documents["PERSONALIZED NEWS FOR YOU"] = f_recent_p.result()
        historical_category_documents["PERSONALIZED NEWS FOR YOU"] = f_hist_p.result()

    for category in recent_category_documents:
        recent_category_documents[category] = remove_duplicates(recent_category_documents[category])

    for category in historical_category_documents:
        historical_category_documents[category] = remove_duplicates(historical_category_documents[category])

    retrieval_time = time.perf_counter() - start_time
    total_chunks = sum(len(docs) for docs in recent_category_documents.values()) + sum(len(docs) for docs in historical_category_documents.values())

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
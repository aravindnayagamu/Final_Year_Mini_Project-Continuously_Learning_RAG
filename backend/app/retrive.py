from record_metrics import update_metrics
from pathlib import Path
import time
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

CUR_DIR = Path(__file__).resolve().parent
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
recent_store = Chroma(
    collection_name="recent_news_docs", embedding_function=embedding_model,
    persist_directory=str(CUR_DIR / "vector_db")
)
historical_store = Chroma(
    collection_name="historical_news_docs", embedding_function=embedding_model,
    persist_directory=str(CUR_DIR / "historical_vector_db")
)



def retrieve_from_store(store, question, k, news_type):
    results = store._collection.query(
        query_texts=[question],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    ids = results["ids"][0]
    relevance_function = store._select_relevance_score_fn()
    retrieved = []

    for record_id, document, metadata, distance in zip(
        ids,
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        retrieved.append({
            "id": record_id,
            "document": document,
            "metadata": metadata or {},
            "distance": distance,
            "relevance": relevance_function(distance),
            "news_type": news_type
        })

    return retrieved


def retrieve_documents(question, k=3):
    start_time = time.perf_counter()
    recent = retrieve_from_store(recent_store, question, k, "RECENT NEWS")
    historical = retrieve_from_store(
        historical_store, question, k, "HISTORICAL NEWS"
    )
    results = recent + historical
    context = "\n\n".join(
        f"[{item['news_type']}]\n"
        f"Source: {item['metadata'].get('source', 'Unknown')}\n"
        f"Downloaded: {item['metadata'].get('paper_retrieval_time', 'Unknown')}\n"
        f"{item['document']}"
        for item in results
    )
    elapsed = time.perf_counter() - start_time
    return results, results, context, elapsed


def show_results(question):
    results, relevant_results, merged_context, retrieval_time = retrieve_documents(question)
    print("\n" + "=" * 80)
    print("QUESTION")
    print("=" * 80)
    print(question)
    print("\n" + "=" * 80)
    print("RETRIEVAL METRICS")
    print("=" * 80)
    print(f"Recent chunks         : {sum(r['news_type'] == 'RECENT NEWS' for r in results)}")
    print(f"Historical chunks     : {sum(r['news_type'] == 'HISTORICAL NEWS' for r in results)}")
    print(f"Total chunks          : {len(results)}")
    print(f"Retrieval time        : {retrieval_time * 1000:.2f} ms")
    print("\n" + "=" * 80)
    print("RETRIEVED CHUNKS")
    print("=" * 80)
    for rank, result in enumerate(results, start=1):
        print(f"\nResult #{rank} - {result['news_type']}")
        print("-" * 80)
        print(f"Distance       : {result['distance']:.4f}")
        print(f"Relevance      : {result['relevance']:.4f}")
        print(f"Source         : {result['metadata'].get('source', 'Unknown')}")
        print(f"Downloaded     : {result['metadata'].get('paper_retrieval_time', 'Unknown')}")
        print("\nContent:")
        print(result["document"])
    print("\n" + "=" * 80)
    print("MERGED CONTEXT")
    print("=" * 80)
    print(merged_context or "No chunks found.")
    return merged_context


if __name__ == "__main__":
    question = input("Enter your question: ")
    show_results(question)
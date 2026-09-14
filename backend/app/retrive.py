import os
from pathlib import Path
import time
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

cur_dir = Path(__file__).resolve().parent
sqlite_url = os.getenv("SQLITE_DB_URL", "")
if sqlite_url.startswith("sqlite:///"):
    raw_path = sqlite_url.replace("sqlite:///", "")
    p = Path(raw_path)
    if not p.is_absolute():
        p = (cur_dir.parent / p).resolve()
    db_dir = p.parent
else:
    db_dir = cur_dir / "vector_db"
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
vector_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(db_dir)
)
def retrieve_documents(question, k=3):
    start_time = time.perf_counter()
    results = vector_store._collection.query(
        query_texts=[question],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )
    end_time = time.perf_counter()
    retrieval_time = end_time - start_time
    relevance_function = vector_store._select_relevance_score_fn()
    retrieved_documents = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        relevance = relevance_function(distance)

        retrieved_documents.append({
            "document": document,
            "metadata": metadata,
            "distance": distance,
            "relevance": relevance
        })

    relevant_documents=retrieved_documents
    '''relevant_documents = [
        result
        for result in retrieved_documents
        if result["relevance"] >= threshold
    ]'''

    merged_context = "\n\n".join(
        result["document"]
        for result in relevant_documents
    )

    return retrieved_documents, relevant_documents, merged_context, retrieval_time

def show_results(question):
    results, relevant_results, merged_context, retrieval_time = (
        retrieve_documents(question)
    )
    print("\n" + "=" * 80)
    print("QUESTION")
    print("=" * 80)
    print(question)
    print("\n" + "=" * 80)
    print("RETRIEVAL METRICS")
    print("=" * 80)
    print(f"Top K                 : {len(results)}")
    print(f"Retrieval time        : {retrieval_time * 1000:.2f} ms")
    print(f"Relevance threshold   : 0.50")
    print(f"Relevant chunks       : {len(relevant_results)}")
    print("\n" + "=" * 80)
    print("RETRIEVED CHUNKS")
    print("=" * 80)
    
    for rank, result in enumerate(results, start=1):
        print(f"\nResult #{rank}")
        print("-" * 80)
        print(
            f"Distance       : "
            f"{result['distance']:.4f}"
        )
        print(
            f"Relevance      : "
            f"{result['relevance']:.4f}"
        )
        print(
            f"Source         : "
            f"{result['metadata'].get('source', 'Unknown')}"
        )
        print(
            f"Start index    : "
            f"{result['metadata'].get('start_index', 'Unknown')}"
        )
        print("\nContent:")
        print(result["document"])

    print("\n" + "=" * 80)
    print("MERGED CONTEXT")
    print("=" * 80)

    if merged_context:
        print(merged_context)
    else:
        print(
            "No chunks passed the relevance threshold."
        )
    return merged_context

if __name__=="__main__":
    question = input("Enter your question: ")
    context = show_results(question)
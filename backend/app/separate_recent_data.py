import os
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)
load_dotenv()

CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
app_dir_name = os.getenv("APP_DIR", "app")
METADATA_DB = PROJECT_DIR / "metadata.db"
BATCH_SIZE = 500

embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
embedding_model = HuggingFaceEmbeddings(
    model_name=embedding_model_name
)

sqlite_db_url = os.getenv("SQLITE_DB_URL", "")
if sqlite_db_url and sqlite_db_url.startswith("sqlite:///"):
    recent_db_dir = (PROJECT_DIR / sqlite_db_url.replace("sqlite:///", "")).parent
else:
    recent_db_dir = PROJECT_DIR / app_dir_name / "vector_db"

historical_db_dir = PROJECT_DIR / app_dir_name / "historical_vector_db"

recent_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(recent_db_dir)
)
historical_store = Chroma(
    collection_name="historical_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(historical_db_dir)
)


def parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def lookup_download_time(metadata):
    value = metadata.get("paper_retrieval_time")
    if value:
        return value
    paper_id = metadata.get("paper_id")
    if not paper_id:
        paper_id = Path(metadata.get("source", "")).stem.rsplit("_", 1)[-1]
    with sqlite3.connect(METADATA_DB) as conn:
        row = conn.execute(
            "SELECT paper_retrieval_time FROM document_metadata WHERE paper_id = ?",
            (paper_id,)
        ).fetchone()
    return row[0] if row else None


def separate_data():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    batch = recent_store._collection.get(
        include=["documents", "metadatas"]
    )

    ids = batch.get("ids", [])
    moved = 0
    recent_count = 0
    unknown_moved = 0
    old_ids = []

    for i, record_id in enumerate(ids):
        document = batch["documents"][i]
        metadata = dict(batch["metadatas"][i] or {})

        timestamp = lookup_download_time(metadata)
        parsed = parse_timestamp(timestamp)

        if timestamp:
            metadata["paper_retrieval_time"] = timestamp

        # Move unknown-timestamp chunks to historical storage.
        if parsed is None:
            historical_store._collection.upsert(
                ids=[record_id],
                documents=[document],
                metadatas=[metadata]
            )
            old_ids.append(record_id)
            unknown_moved += 1
            continue

        # Move chunks older than 24 hours to historical storage.
        if parsed < cutoff:
            historical_store._collection.upsert(
                ids=[record_id],
                documents=[document],
                metadatas=[metadata]
            )
            old_ids.append(record_id)
            moved += 1

        # Retain chunks downloaded within the last 24 hours.
        else:
            recent_store._collection.update(
                ids=[record_id],
                metadatas=[metadata]
            )
            recent_count += 1

    # Delete from the recent DB only after destination upserts succeed.
    if old_ids:
        recent_store._collection.delete(ids=old_ids)

    print(f"Historical chunks moved (older than 24 hours): {moved}")
    print(f"Unknown-time chunks moved to historical DB: {unknown_moved}")
    print(f"Total historical chunks moved: {moved + unknown_moved}")
    print(f"Recent chunks retained: {recent_count}")


if __name__ == "__main__":
    separate_data()
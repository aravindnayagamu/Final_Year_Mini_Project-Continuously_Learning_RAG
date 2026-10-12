import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

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


_paper_time_cache = {}


def _get_pg_conn():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None
    sync_url = db_url.replace("+asyncpg", "")
    try:
        import psycopg2
        return psycopg2.connect(sync_url)
    except Exception:
        return None


def lookup_download_time(metadata):
    value = metadata.get("paper_retrieval_time")
    if value:
        return value
    paper_id = metadata.get("paper_id")
    if not paper_id:
        paper_id = Path(metadata.get("source", "")).stem.rsplit("_", 1)[-1]
    if paper_id in _paper_time_cache:
        return _paper_time_cache[paper_id]

    pg_conn = _get_pg_conn()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    "SELECT retrieval_time FROM documents WHERE paper_id = %s",
                    (paper_id,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    res = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                    _paper_time_cache[paper_id] = res
                    return res
        except Exception:
            pass
        finally:
            pg_conn.close()

    if METADATA_DB.exists():
        with sqlite3.connect(METADATA_DB) as conn:
            row = conn.execute(
                "SELECT paper_retrieval_time FROM document_metadata WHERE paper_id = ?",
                (paper_id,)
            ).fetchone()
        res = row[0] if row else None
        _paper_time_cache[paper_id] = res
        return res

    _paper_time_cache[paper_id] = None
    return None


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

    hist_ids = []
    hist_docs = []
    hist_metas = []

    update_ids = []
    update_metas = []

    for i, record_id in enumerate(ids):
        document = batch["documents"][i]
        metadata = dict(batch["metadatas"][i] or {})

        timestamp = lookup_download_time(metadata)
        parsed = parse_timestamp(timestamp)

        if timestamp:
            metadata["paper_retrieval_time"] = timestamp

        if parsed is None:
            hist_ids.append(record_id)
            hist_docs.append(document)
            hist_metas.append(metadata)
            old_ids.append(record_id)
            unknown_moved += 1
            continue

        if parsed < cutoff:
            hist_ids.append(record_id)
            hist_docs.append(document)
            hist_metas.append(metadata)
            old_ids.append(record_id)
            moved += 1
        else:
            update_ids.append(record_id)
            update_metas.append(metadata)
            recent_count += 1

    for i in range(0, len(hist_ids), 200):
        historical_store._collection.upsert(
            ids=hist_ids[i:i+200],
            documents=hist_docs[i:i+200],
            metadatas=hist_metas[i:i+200]
        )

    for i in range(0, len(update_ids), 200):
        recent_store._collection.update(
            ids=update_ids[i:i+200],
            metadatas=update_metas[i:i+200]
        )

    if old_ids:
        for i in range(0, len(old_ids), 200):
            recent_store._collection.delete(ids=old_ids[i:i+200])

    print(f"Historical chunks moved (older than 24 hours): {moved}")
    print(f"Unknown-time chunks moved to historical DB: {unknown_moved}")
    print(f"Total historical chunks moved: {moved + unknown_moved}")
    print(f"Recent chunks retained: {recent_count}")


if __name__ == "__main__":
    separate_data()
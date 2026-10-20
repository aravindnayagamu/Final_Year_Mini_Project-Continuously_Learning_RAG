import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import time
from pypdf import PdfReader
from pathlib import Path
import shutil
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import sqlite3
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)
load_dotenv()

cur_dir = Path(__file__)
base_dir = cur_dir.resolve().parent.parent
app_dir_name = os.getenv("APP_DIR", "app")

unread_dir = base_dir / app_dir_name / 'news_database' / 'unread'
read_dir = base_dir / app_dir_name / 'news_database' / 'read'

sqlite_db_url = os.getenv("SQLITE_DB_URL", "")
if sqlite_db_url and sqlite_db_url.startswith("sqlite:///"):
    db_dir = (base_dir / sqlite_db_url.replace("sqlite:///", "")).parent
else:
    db_dir = base_dir / app_dir_name / 'vector_db'

metadata_db = base_dir / 'metadata.db'
db_dir.mkdir(parents=True, exist_ok=True)

embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
embedding_model = HuggingFaceEmbeddings(
    model_name=embedding_model_name
)
vector_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(db_dir)
)

_meta_cache = {}


def extract_text(path):
    reader=PdfReader(path)
    full_text=""
    for pages in reader.pages:
        text=pages.extract_text()
        if text:
            full_text+=text+"\n"
    return full_text

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

def get_article_metadata(file_name):
    paper_id = Path(file_name).stem.rsplit("_", 1)[-1]
    if paper_id in _meta_cache:
        return _meta_cache[paper_id]

    pg_conn = _get_pg_conn()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    "SELECT source_name, retrieval_time, title FROM documents WHERE paper_id = %s",
                    (paper_id,)
                )
                row = cur.fetchone()
                if row:
                    rt = row[1].isoformat() if hasattr(row[1], "isoformat") else (str(row[1]) if row[1] else None)
                    res = (paper_id, row[0], rt)
                    _meta_cache[paper_id] = res
                    return res
        except Exception:
            pass
        finally:
            pg_conn.close()

    if metadata_db.exists():
        with sqlite3.connect(metadata_db) as conn:
            row = conn.execute(
                "SELECT source_name, paper_retrieval_time FROM document_metadata WHERE paper_id = ?",
                (paper_id,)
            ).fetchone()
        if row:
            res = (paper_id, row[0], row[1])
            _meta_cache[paper_id] = res
            return res

    res = (paper_id, "Unknown", None)
    _meta_cache[paper_id] = res
    return res


def chunk_text(text, file_name):
    text = text.strip()
    if not text:
        return []

    paper_id, source_name, retrieval_time = get_article_metadata(file_name)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=300, add_start_index=True
    )
    doc = Document(
        page_content=text,
        metadata={
            "source": file_name,
            "paper_id": paper_id,
            "source_name": source_name,
            "paper_retrieval_time": retrieval_time
        }
    )
    all_splits = text_splitter.split_documents([doc])
    cleaned_splits = []
    for chunk in all_splits:
        if chunk.page_content and chunk.page_content.strip():
            chunk.page_content = chunk.page_content.strip()
            cleaned_splits.append(chunk)
    return cleaned_splits


def process_unread_files():
    unread_dir.mkdir(parents=True, exist_ok=True)
    read_dir.mkdir(parents=True, exist_ok=True)

    deadline_raw = os.getenv("INGEST_VECTORIZE_DEADLINE")
    deadline = float(deadline_raw) if deadline_raw else None

    batch_texts = []
    batch_metadatas = []
    batch_files = []
    max_files = 150
    files_processed = 0

    for file in list(unread_dir.iterdir()):
        if files_processed >= max_files:
            break
        if deadline is not None and time.time() >= deadline:
            print("Time budget reached; remaining files will be processed in the next run.")
            break

        if file.suffix.lower() != ".pdf":
            continue

        if not file.exists():
            continue

        try:
            text = extract_text(file)
            chunks = chunk_text(text, file.name)
            for chunk in chunks:
                t = str(chunk.page_content).encode("utf-8", errors="ignore").decode("utf-8")
                if t.strip():
                    batch_texts.append(t)
                    batch_metadatas.append(chunk.metadata)
            batch_files.append(file)
            files_processed += 1

            if len(batch_texts) >= 50:
                vector_store.add_texts(texts=batch_texts, metadatas=batch_metadatas)
                print(f"Embedded {len(batch_texts)} chunks.")
                for f in batch_files:
                    if f.exists():
                        shutil.move(str(f), str(read_dir / f.name))
                batch_texts.clear()
                batch_metadatas.clear()
                batch_files.clear()

        except Exception as exc:
            print(f"Skipping file {file.name}: {exc}")

    if batch_texts:
        vector_store.add_texts(texts=batch_texts, metadatas=batch_metadatas)
        print(f"Embedded {len(batch_texts)} chunks.")
        for f in batch_files:
            if f.exists():
                shutil.move(str(f), str(read_dir / f.name))


process_unread_files()
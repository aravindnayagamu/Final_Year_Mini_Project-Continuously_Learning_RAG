import os
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



def extract_text(path):
    reader=PdfReader(path)
    full_text=""
    for pages in reader.pages:
        text=pages.extract_text()
        if text:
            full_text+=text+"\n"
    return full_text

def get_article_metadata(file_name):
    paper_id = Path(file_name).stem.rsplit("_", 1)[-1]
    with sqlite3.connect(metadata_db) as conn:
        row = conn.execute(
            "SELECT source_name, paper_retrieval_time FROM document_metadata WHERE paper_id = ?",
            (paper_id,)
        ).fetchone()
    if row:
        return paper_id, row[0], row[1]
    return paper_id, "Unknown", None


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
    #print(f"The type of the chunk after splitting is {type(cleaned_splits[0])}")
    return cleaned_splits


def process_unread_files():
    unread_dir.mkdir(parents=True, exist_ok=True)
    read_dir.mkdir(parents=True, exist_ok=True)

    deadline_raw = os.getenv("INGEST_VECTORIZE_DEADLINE")
    deadline = float(deadline_raw) if deadline_raw else None

    for file in list(unread_dir.iterdir()):
        if deadline is not None and time.time() >= deadline:
            print("Time budget reached; remaining files will be processed in the next run.")
            break

        if file.suffix.lower() != ".pdf":
            continue

        if not file.exists():
            print(f"Skipping missing file: {file.name}")
            continue

        try:
            text = extract_text(file)
            text_chunk = chunk_text(text, file.name)
            embedded_text(text_chunk)

            if file.exists():
                dest = read_dir / file.name
                shutil.move(str(file), str(dest))
                print(f"Processed and moved: {file.name}")

        except FileNotFoundError:
            print(f"File no longer exists; skipping: {file.name}")

    return


def embedded_text(chunks):
    if not chunks:
        print("No valid chunks to embed.")
        return

    texts = []
    metadatas = []

    for chunk in chunks:
        text = str(chunk.page_content)
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        if not text.strip():
            continue

        texts.append(text)
        metadatas.append(chunk.metadata)

    if not texts:
        print("No valid text to embed.")
        return

    vector_store.add_texts(
        texts=texts,
        metadatas=metadatas
    )
    print(f"Embedded {len(texts)} chunks.")


process_unread_files()
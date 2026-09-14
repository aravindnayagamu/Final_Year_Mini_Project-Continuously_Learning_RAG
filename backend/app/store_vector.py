import os
from pypdf import PdfReader
from pathlib import Path
import shutil
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

cur_dir = Path(__file__).resolve().parent
base_dir = cur_dir.parent

sqlite_url = os.getenv("SQLITE_DB_URL", "")
if sqlite_url.startswith("sqlite:///"):
    raw_path = sqlite_url.replace("sqlite:///", "")
    p = Path(raw_path)
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    db_dir = p.parent
else:
    db_dir = base_dir / "app" / "vector_db"

unread_dir = base_dir / "app" / "news_database" / "unread"
read_dir = base_dir / "app" / "news_database" / "read"

unread_dir.mkdir(parents=True, exist_ok=True)
read_dir.mkdir(parents=True, exist_ok=True)
db_dir.mkdir(parents=True, exist_ok=True)

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
vector_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(db_dir)
)

def extract_text(path):
    reader = PdfReader(path)
    full_text = ""
    for pages in reader.pages:
        text = pages.extract_text()
        if text:
            full_text += text + "\n"
    return full_text

def chunk_text(text, file_name):
    text = text.strip()
    if not text:
        return []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, add_start_index=True
    )
    doc = Document(page_content=text, metadata={"source": file_name, "doc_type": "news"})
    all_splits = text_splitter.split_documents([doc])
    cleaned_splits = []
    for chunk in all_splits:
        if chunk.page_content and chunk.page_content.strip():
            chunk.page_content = chunk.page_content.strip()
            cleaned_splits.append(chunk)
    return cleaned_splits

def embedded_text(chunks):
    if not chunks:
        print("No valid chunks to embed.")
        return 0

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
        return 0

    vector_store.add_texts(
        texts=texts,
        metadatas=metadatas
    )
    print(f"Embedded {len(texts)} chunks.")
    return len(texts)

def process_unread_files():
    unread_dir.mkdir(parents=True, exist_ok=True)
    read_dir.mkdir(parents=True, exist_ok=True)
    processed_count = 0
    for file in unread_dir.iterdir():
        if file.suffix.lower() == ".pdf":
            text = extract_text(file)
            text_chunk = chunk_text(text, file.name)
            embedded_text(text_chunk)
            dest = read_dir / file.name
            if dest.exists():
                dest.unlink()
            shutil.move(file, dest)
            processed_count += 1
    return processed_count

if __name__ == "__main__":
    process_unread_files()
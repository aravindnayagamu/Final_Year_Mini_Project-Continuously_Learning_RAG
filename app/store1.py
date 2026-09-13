from pypdf import PdfReader
from pathlib import Path
import shutil

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


# -------------------------
# Paths
# -------------------------

cur_dir = Path(__file__).resolve().parent

unread_dir = cur_dir / "news_database" / "unread"
read_dir = cur_dir / "news_database" / "read"

recent_db_dir = cur_dir / "vector_db" / "recent"
recent_db_dir.mkdir(parents=True, exist_ok=True)
recent_db_dir.mkdir(
    parents=True,
    exist_ok=True
)


# -------------------------
# Embedding model
# -------------------------

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# -------------------------
# Chroma
# -------------------------

recent_store = Chroma(
    collection_name="recent_news_docs",
    embedding_function=embedding_model,
    persist_directory=str(recent_db_dir)
)


# -------------------------
# PDF extraction
# -------------------------

def extract_text(path):

    reader = PdfReader(path)

    full_text = ""

    for page in reader.pages:

        text = page.extract_text()

        if text:
            full_text += text + "\n"

    return full_text


# -------------------------
# Chunking
# -------------------------

def chunk_text(text, file_name):

    text = text.strip()

    if not text:
        return []

    paper_id = Path(file_name).stem

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        add_start_index=True
    )

    doc = Document(
        page_content=text,
        metadata={
            "paper_id": paper_id,
            "source": file_name
        }
    )

    chunks = text_splitter.split_documents([doc])

    cleaned_chunks = []

    for i, chunk in enumerate(chunks):

        if not chunk.page_content.strip():
            continue

        chunk.page_content = chunk.page_content.strip()

        chunk.metadata["chunk_id"] = (
            f"{paper_id}_{i:05d}"
        )

        chunk.metadata["chunk_index"] = i

        chunk.metadata["memory_tier"] = "recent"

        cleaned_chunks.append(chunk)

    return cleaned_chunks


# -------------------------
# Store in Chroma
# -------------------------

def store_chunks(chunks):

    if not chunks:
        print("No valid chunks to store.")
        return

    ids = [
        chunk.metadata["chunk_id"]
        for chunk in chunks
    ]

    recent_store.add_documents(
        documents=chunks,
        ids=ids
    )

    print(f"Stored {len(chunks)} chunks.")


# -------------------------
# Process PDFs
# -------------------------

def process_unread_files():

    for file in unread_dir.iterdir():

        if file.suffix.lower() != ".pdf":
            continue

        try:

            print(f"Processing {file.name}")

            text = extract_text(file)

            chunks = chunk_text(
                text,
                file.name
            )

            store_chunks(chunks)

            shutil.move(
                file,
                read_dir / file.name
            )

            print(
                f"Successfully processed {file.name}"
            )

        except Exception as e:

            print(
                f"Failed to process "
                f"{file.name}: {e}"
            )


process_unread_files()
import os
from pypdf import PdfReader
from pathlib import Path
import shutil
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


cur_dir=Path(__file__)
#print(cur_dir)
base_dir=cur_dir.resolve().parent.parent
unread_dir=base_dir/'app'/'news_database'/'unread'
read_dir=base_dir/'app'/'news_database'/'read'
db_dir = base_dir / 'app' / 'vector_db'
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
    reader=PdfReader(path)
    full_text=""
    for pages in reader.pages:
        text=pages.extract_text()
        if text:
            full_text+=text+"\n"
    return full_text

def chunk_text(text, file_name):
    text = text.strip()
    if not text:
        return []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=300, add_start_index=True
    )
    doc = Document(page_content=text, metadata={"source": file_name})
    all_splits = text_splitter.split_documents([doc])
    cleaned_splits = []
    for chunk in all_splits:
        if chunk.page_content and chunk.page_content.strip():
            chunk.page_content = chunk.page_content.strip()
            cleaned_splits.append(chunk)
    #print(f"The type of the chunk after splitting is {type(cleaned_splits[0])}")
    return cleaned_splits

def process_unread_files():
    for file in unread_dir.iterdir():
        
        if file.suffix.lower()=='.pdf':
            text=extract_text(file)
            #print(f"Read {file.name} with {len(text)} characters")
            #print(text[:1000])
            text_chunk=chunk_text(text,file.name)
            #print(type(text_chunk))
            text_embedded=embedded_text(text_chunk)
            dest=read_dir/file.name
            shutil.move(file,dest)
            
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

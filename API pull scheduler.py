import time
import logging
import feedparser
import schedule
import re
import os
import sqlite3
import hashlib
from datetime import datetime
import concurrent.futures

# Configure thread-safe logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
DATA_DIR = "./news_data/unread"
TRACKER_DB = "tracker.db"
METADATA_DB = "metadata.db"

# List of dictionaries to easily map URLs to their Source Names
RSS_SOURCES = [
    {
        "source_name": "TOI_Top_Stories",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    },
    {
        "source_name": "NDTV_Top_Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories" 
    },
    {
        "source_name": "PIB_India",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3" # Press Information Bureau (GoI)
    }
]

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def init_databases():
    """
    Creates the necessary tables in both SQLite databases if they don't exist.
    """
    # 1. Database to track what we've seen (used for pre-emptive stopping)
    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seen_items (
                original_id TEXT PRIMARY KEY
            )
        ''')
        conn.commit()

    # 2. Database to store metadata for the RAG system
    with sqlite3.connect(METADATA_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_metadata (
                paper_id TEXT PRIMARY KEY,
                source_name TEXT,
                paper_retrieval_time TEXT
            )
        ''')
        conn.commit()

# Run initialization on startup
init_databases()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def clean_html(raw_html):
    """Strips HTML and CDATA for clean text extraction."""
    if not raw_html:
        return ""
    clean_text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', raw_html)
    clean_text = re.sub(r'<.*?>', '', clean_text)
    return re.sub(r'\s+', ' ', clean_text).strip()

def generate_paper_id(original_id):
    """Generates a safe, unique filename/paper_id using MD5 hash of the URL/GUID."""
    return hashlib.md5(original_id.encode('utf-8')).hexdigest()

def is_item_seen(original_id):
    """Checks the tracker database to see if we've already processed this item."""
    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_items WHERE original_id = ?", (original_id,))
        return cursor.fetchone() is not None

def mark_item_seen_and_save_metadata(original_id, paper_id, source_name):
    """Records the item in the tracker and saves its metadata atomically."""
    retrieval_time = datetime.now().isoformat()
    
    with sqlite3.connect(TRACKER_DB) as conn_tracker:
        conn_tracker.cursor().execute(
            "INSERT OR IGNORE INTO seen_items (original_id) VALUES (?)", (original_id,)
        )
        conn_tracker.commit()

    with sqlite3.connect(METADATA_DB) as conn_meta:
        conn_meta.cursor().execute(
            "INSERT OR IGNORE INTO document_metadata (paper_id, source_name, paper_retrieval_time) VALUES (?, ?, ?)",
            (paper_id, source_name, retrieval_time)
        )
        conn_meta.commit()

def save_text_file(paper_id, title, content, source_name):
    """Writes the parsed text to a .txt file."""
    # Clean the source name to ensure it's safe for file paths
    safe_source = re.sub(r'[\\/*?:"<>|]', "", source_name)
    filepath = os.path.join(DATA_DIR, f"{safe_source}_{paper_id}.txt")
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\n\n")
            f.write(f"Content: {content}\n")
    except Exception as e:
        logging.error(f"Failed to save text file {safe_source}_{paper_id}.txt: {e}")

# ---------------------------------------------------------
# WORKER FUNCTIONS (Run in separate threads)
# ---------------------------------------------------------
def process_rss_feed(source_config):
    """
    Thread worker for processing a single RSS feed.
    """
    source_name = source_config['source_name']
    url = source_config['url']
    
    logging.info(f"[{source_name}] Starting RSS fetch...")
    try:
        parsed_feed = feedparser.parse(url)
    except Exception as e:
        logging.error(f"[{source_name}] Error parsing feed: {e}")
        return

    new_items_count = 0

    for entry in parsed_feed.entries:
        # Fallback to link if guid doesn't exist
        original_id = getattr(entry, 'guid', getattr(entry, 'link', None))
        if not original_id:
            continue
            
        # EARLY STOPPING: Because RSS feeds are chronological (newest first),
        # if we hit an ID we already have in the database, we can assume
        # we have already processed everything older than this.
        if is_item_seen(original_id):
            logging.info(f"[{source_name}] Found already-seen item. Pre-emptively stopping feed iteration.")
            break 
            
        # Extract and clean
        title = getattr(entry, 'title', 'No Title')
        description = clean_html(getattr(entry, 'description', ''))
        
        # Generate unique paper ID
        paper_id = generate_paper_id(original_id)
        
        # Save to File (Updated with source_name)
        save_text_file(paper_id, title, description, source_name)
        
        # Update Databases
        mark_item_seen_and_save_metadata(original_id, paper_id, source_name)
        new_items_count += 1

    logging.info(f"[{source_name}] Finished. Added {new_items_count} new articles.")

# ---------------------------------------------------------
# MULTI-THREADED JOB MANAGER
# ---------------------------------------------------------
def run_all_scrapers():
    """
    Fires off all scrapers concurrently using a ThreadPool.
    Each RSS feed and API call runs in its own thread to maximize speed.
    """
    logging.info("--- Starting scheduled multi-source data ingestion ---")
    
    # We use ThreadPoolExecutor to handle the threads safely and efficiently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        
        # Submit RSS jobs
        for source in RSS_SOURCES:
            executor.submit(process_rss_feed, source)
        
    logging.info("--- All ingestion threads completed ---")


# ---------------------------------------------------------
# MAIN EXECUTION & SCHEDULING
# ---------------------------------------------------------
if __name__ == "__main__":
    # Run once immediately upon starting
    run_all_scrapers()

    # Schedule to run every 30 minutes
    schedule.every(30).minutes.do(run_all_scrapers)
    
    logging.info("Scheduler is active. Fetching every 30 minutes. Press Ctrl+C to exit.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60) # Wake up every 60 seconds to check if a job is due
    except KeyboardInterrupt:
        logging.info("Program gracefully terminated by user.")
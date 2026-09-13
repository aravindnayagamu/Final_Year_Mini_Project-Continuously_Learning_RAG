import time
import logging
import feedparser
import schedule
import re
import sqlite3
import hashlib
from datetime import datetime
import concurrent.futures

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from xml.sax.saxutils import escape


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
)


# ============================================================
# PATHS
# ============================================================

# Directory containing this Python file
#
# .../continuously_learning_rag/app/
CUR_DIR = Path(__file__).resolve().parent

# Project root
#
# .../continuously_learning_rag/
PROJECT_DIR = CUR_DIR.parent

# Folder where newly fetched PDFs are stored
#
# .../continuously_learning_rag/app/news_database/unread/
DATA_DIR = CUR_DIR / "news_database" / "unread"

# Databases
TRACKER_DB = PROJECT_DIR / "tracker.db"
METADATA_DB = PROJECT_DIR / "metadata.db"


# Create unread directory if it doesn't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# RSS SOURCES
# ============================================================

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
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
    }
]


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_databases():

    # --------------------------------------------------------
    # Tracker database
    # --------------------------------------------------------

    with sqlite3.connect(TRACKER_DB) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (
                original_id TEXT PRIMARY KEY
            )
        """)

        conn.commit()


    # --------------------------------------------------------
    # Metadata database
    # --------------------------------------------------------

    with sqlite3.connect(METADATA_DB) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_metadata (
                paper_id TEXT PRIMARY KEY,
                source_name TEXT,
                paper_retrieval_time TEXT
            )
        """)

        conn.commit()


# Initialize databases when program starts
init_databases()


# ============================================================
# CLEAN HTML
# ============================================================

def clean_html(raw_html):

    if not raw_html:
        return ""

    # Remove CDATA wrapper
    clean_text = re.sub(
        r'<!\[CDATA\[(.*?)\]\]>',
        r'\1',
        raw_html,
        flags=re.DOTALL
    )

    # Remove HTML tags
    clean_text = re.sub(
        r'<.*?>',
        '',
        clean_text
    )

    # Normalize whitespace
    clean_text = re.sub(
        r'\s+',
        ' ',
        clean_text
    )

    return clean_text.strip()


# ============================================================
# GENERATE STABLE PAPER ID
# ============================================================

def generate_paper_id(original_id):

    return hashlib.md5(
        original_id.encode("utf-8")
    ).hexdigest()


# ============================================================
# CHECK WHETHER ARTICLE WAS ALREADY SEEN
# ============================================================

def is_item_seen(original_id):

    with sqlite3.connect(TRACKER_DB) as conn:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM seen_items
            WHERE original_id = ?
            """,
            (original_id,)
        )

        return cursor.fetchone() is not None


# ============================================================
# SAVE TRACKING + METADATA
# ============================================================

def mark_item_seen_and_save_metadata(
    original_id,
    paper_id,
    source_name
):

    retrieval_time = datetime.now().isoformat()


    # --------------------------------------------------------
    # Save to tracker database
    # --------------------------------------------------------

    with sqlite3.connect(TRACKER_DB) as conn:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO seen_items
            (original_id)
            VALUES (?)
            """,
            (original_id,)
        )

        conn.commit()


    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    with sqlite3.connect(METADATA_DB) as conn:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO document_metadata
            (
                paper_id,
                source_name,
                paper_retrieval_time
            )
            VALUES (?, ?, ?)
            """,
            (
                paper_id,
                source_name,
                retrieval_time
            )
        )

        conn.commit()


# ============================================================
# SAVE ARTICLE AS PDF
# ============================================================

def save_pdf_file(
    paper_id,
    title,
    content,
    source_name
):

    # --------------------------------------------------------
    # Clean source name for use in filename
    # --------------------------------------------------------

    safe_source = re.sub(
        r'[\\/*?:"<>|]',
        "",
        source_name
    )


    # --------------------------------------------------------
    # PDF path
    # --------------------------------------------------------

    filepath = DATA_DIR / f"{safe_source}_{paper_id}.pdf"


    try:

        # ----------------------------------------------------
        # Create PDF document
        # ----------------------------------------------------

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )


        # ----------------------------------------------------
        # Styles
        # ----------------------------------------------------

        styles = getSampleStyleSheet()

        title_style = styles["Title"]
        body_style = styles["BodyText"]

        title_style.alignment = TA_LEFT


        # ----------------------------------------------------
        # PDF content
        # ----------------------------------------------------

        story = []


        # Title
        story.append(
            Paragraph(
                escape(title),
                title_style
            )
        )

        story.append(
            Spacer(1, 15)
        )


        # Source
        story.append(
            Paragraph(
                f"<b>Source:</b> {escape(source_name)}",
                body_style
            )
        )

        story.append(
            Spacer(1, 10)
        )


        # Article content
        #
        # Escape special HTML characters because ReportLab's
        # Paragraph interprets text as XML/HTML.
        #
        escaped_content = escape(content)


        # Convert newlines into paragraph breaks
        paragraphs = escaped_content.split("\n")


        for paragraph in paragraphs:

            paragraph = paragraph.strip()

            if not paragraph:
                continue

            story.append(
                Paragraph(
                    paragraph,
                    body_style
                )
            )

            story.append(
                Spacer(1, 8)
            )


        # ----------------------------------------------------
        # Generate the actual PDF
        # ----------------------------------------------------

        doc.build(story)


        logging.info(
            f"[{source_name}] "
            f"Saved PDF: {filepath.name}"
        )

        return True


    except Exception as e:

        logging.error(
            f"[{source_name}] "
            f"Failed to save PDF {filepath.name}: {e}"
        )

        # If a partially-created PDF exists, remove it
        if filepath.exists():

            try:
                filepath.unlink()

            except Exception:
                pass

        return False


# ============================================================
# PROCESS ONE RSS FEED
# ============================================================

def process_rss_feed(source_config):

    source_name = source_config["source_name"]
    url = source_config["url"]


    logging.info(
        f"[{source_name}] Starting RSS fetch..."
    )


    # --------------------------------------------------------
    # Parse RSS feed
    # --------------------------------------------------------

    try:

        parsed_feed = feedparser.parse(url)

    except Exception as e:

        logging.error(
            f"[{source_name}] "
            f"Error parsing feed: {e}"
        )

        return


    # --------------------------------------------------------
    # Check whether feed contains articles
    # --------------------------------------------------------

    if not parsed_feed.entries:

        logging.warning(
            f"[{source_name}] "
            f"No entries found."
        )

        return


    new_items_count = 0


    # --------------------------------------------------------
    # Process every RSS entry
    # --------------------------------------------------------

    for entry in parsed_feed.entries:


        # ----------------------------------------------------
        # Get unique article identifier
        # ----------------------------------------------------

        original_id = getattr(
            entry,
            "guid",
            getattr(entry, "link", None)
        )


        if not original_id:

            logging.warning(
                f"[{source_name}] "
                f"Skipping item without GUID/link."
            )

            continue


        # ----------------------------------------------------
        # Check duplicate
        # ----------------------------------------------------

        if is_item_seen(original_id):

            logging.info(
                f"[{source_name}] "
                f"Found already-seen article. "
                f"Stopping feed iteration."
            )

            break


        # ----------------------------------------------------
        # Extract title
        # ----------------------------------------------------

        title = getattr(
            entry,
            "title",
            "No Title"
        )


        # ----------------------------------------------------
        # Extract RSS description
        # ----------------------------------------------------

        description = clean_html(
            getattr(
                entry,
                "description",
                ""
            )
        )


        # ----------------------------------------------------
        # Generate stable paper ID
        # ----------------------------------------------------

        paper_id = generate_paper_id(
            original_id
        )


        # ----------------------------------------------------
        # Create PDF
        # ----------------------------------------------------

        saved = save_pdf_file(
            paper_id,
            title,
            description,
            source_name
        )


        # ----------------------------------------------------
        # Only mark article as seen AFTER successful PDF
        # creation.
        # ----------------------------------------------------

        if saved:

            mark_item_seen_and_save_metadata(
                original_id,
                paper_id,
                source_name
            )

            new_items_count += 1


    logging.info(
        f"[{source_name}] "
        f"Finished. "
        f"Added {new_items_count} new articles."
    )


# ============================================================
# RUN ALL RSS SCRAPERS
# ============================================================

def run_all_scrapers():

    logging.info(
        "\n"
        "============================================================\n"
        "Starting multi-source news ingestion\n"
        "============================================================"
    )


    # --------------------------------------------------------
    # Create one worker per RSS source
    # --------------------------------------------------------

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(RSS_SOURCES)
    ) as executor:


        futures = []


        # Submit all RSS sources concurrently
        for source in RSS_SOURCES:

            future = executor.submit(
                process_rss_feed,
                source
            )

            futures.append(future)


        # ----------------------------------------------------
        # Wait for all threads to finish
        # ----------------------------------------------------

        for future in futures:

            try:

                future.result()

            except Exception as e:

                logging.error(
                    f"Worker thread failed: {e}"
                )


    logging.info(
        "============================================================\n"
        "All ingestion threads completed\n"
        "============================================================"
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

if __name__ == "__main__":

    logging.info(
        "News fetcher started."
    )


    # --------------------------------------------------------
    # 1. FETCH IMMEDIATELY
    # --------------------------------------------------------

    run_all_scrapers()


    # --------------------------------------------------------
    # 2. SCHEDULE NEXT FETCH
    # --------------------------------------------------------

    schedule.every(20).minutes.do(
        run_all_scrapers
    )


    logging.info(
        "Scheduler is active."
    )

    logging.info(
        "Next fetch will happen in 20 minutes."
    )


    # --------------------------------------------------------
    # 3. KEEP PROGRAM ALIVE
    # --------------------------------------------------------

    try:

        while True:

            schedule.run_pending()

            time.sleep(1)


    except KeyboardInterrupt:

        logging.info(
            "News fetcher gracefully terminated."
        )
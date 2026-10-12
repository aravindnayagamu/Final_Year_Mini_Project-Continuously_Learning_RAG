import time
import os
from dotenv import load_dotenv
import logging
import urllib.request
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
)

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)
load_dotenv()

CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
app_dir_name = os.getenv("APP_DIR", "app")
DATA_DIR = PROJECT_DIR / app_dir_name / "news_database" / "unread"

TRACKER_DB = PROJECT_DIR / "tracker.db"
METADATA_DB = PROJECT_DIR / "metadata.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)


RSS_SOURCES = [
    {
        "source_name": "TOI_Top_Stories",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    },
    {
        "source_name": "TOI_Most_Recent",
        "url": "http://timesofindia.indiatimes.com/rssfeedmostrecent.cms"
    },
    {
        "source_name": "TOI_India",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"
    },
    {
        "source_name": "TOI_World",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/296589292.cms"
    },
    {
        "source_name": "TOI_NRI",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/7098551.cms"
    },
    {
        "source_name": "TOI_Business",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/1898055.cms"
    },
    {
        "source_name": "TOI_US",
        "url": "https://timesofindia.indiatimes.com/rssfeeds_us/72258322.cms"
    },
    {
        "source_name": "TOI_Cricket",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/54829575.cms"
    },
    {
        "source_name": "TOI_Sports",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/4719148.cms"
    },
    {
        "source_name": "TOI_Science",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128672765.cms"
    },
    {
        "source_name": "TOI_Environment",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/2647163.cms"
    },
    {
        "source_name": "TOI_Tech",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/66949542.cms"
    },
    {
        "source_name": "TOI_Education",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/913168846.cms"
    },
    {
        "source_name": "TOI_Entertainment",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/1081479906.cms"
    },
    {
        "source_name": "TOI_LifeStyle",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/2886704.cms"
    },
    {
        "source_name": "TOI_Astrology",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/65857041.cms"
    },
    {
        "source_name": "TOI_Automobiles",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/74317216.cms"
    },
    {
        "source_name": "TOI_Mumbai",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms"
    },
    {
        "source_name": "TOI_Delhi",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128839596.cms"
    },
    {
        "source_name": "TOI_Chennai",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/2950623.cms"
    },
    {
        "source_name": "TOI_Kolkata",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128830821.cms"
    },
    {
        "source_name": "NDTV_Top_Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories"
    },
    {
        "source_name": "NDTV_Latest_Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-latest"
    },
    {
        "source_name": "NDTV_Trending_Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-trending-news"
    },
    {
        "source_name": "NDTV_India",
        "url": "https://feeds.feedburner.com/ndtvnews-india-news"
    },
    {
        "source_name": "NDTV_World",
        "url": "https://feeds.feedburner.com/ndtvnews-world-news"
    },
    {
        "source_name": "NDTV_Business",
        "url": "https://feeds.feedburner.com/ndtvprofit-latest"
    },
    {
        "source_name": "NDTV_Movies",
        "url": "https://feeds.feedburner.com/ndtvmovies-latest"
    },
    {
        "source_name": "NDTV_Sports",
        "url": "https://feeds.feedburner.com/ndtvsports-latest"
    },
    {
        "source_name": "NDTV_Cricket",
        "url": "https://feeds.feedburner.com/ndtvsports-cricket"
    },
    {
        "source_name": "NDTV_Tech",
        "url": "https://feeds.feedburner.com/gadgets360-latest"
    },
    {
        "source_name": "NDTV_Automobiles",
        "url": "https://feeds.feedburner.com/carandbike-latest"
    },
    {
        "source_name": "NDTV_Cities",
        "url": "https://feeds.feedburner.com/ndtvnews-cities-news"
    },
    {
        "source_name": "NDTV_South",
        "url": "https://feeds.feedburner.com/ndtvnews-south"
    },
    {
        "source_name": "NDTV_NRI",
        "url": "https://feeds.feedburner.com/ndtvnews-indians-abroad"
    },
    {
        "source_name": "NDTV_Health",
        "url": "https://feeds.feedburner.com/ndtvcooks-latest"
    },
    {
        "source_name": "NDTV_Offbeat",
        "url": "https://feeds.feedburner.com/ndtvnews-offbeat-news"
    },
    {
        "source_name": "NDTV_People",
        "url": "https://feeds.feedburner.com/ndtvnews-people"
    },
    {
        "source_name": "PIB_India",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
    }
]


def init_databases():
    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (original_id TEXT PRIMARY KEY)
        """)

        conn.commit()


    with sqlite3.connect(METADATA_DB) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_metadata (paper_id TEXT PRIMARY KEY,source_name TEXT,paper_retrieval_time TEXT)
        """)

        conn.commit()
init_databases()


def clean_html(raw_html):
    if not raw_html:
        return ""

    clean_text = re.sub(
        r'<!\[CDATA\[(.*?)\]\]>',
        r'\1',
        raw_html,
        flags=re.DOTALL
    )

    clean_text = re.sub(
        r'<.*?>',
        '',
        clean_text
    )

    clean_text = re.sub(
        r'\s+',
        ' ',
        clean_text
    )

    return clean_text.strip()

def generate_paper_id(original_id):
    return hashlib.md5(original_id.encode("utf-8")).hexdigest()


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


def mark_item_seen_and_save_metadata(original_id,paper_id,source_name):
    retrieval_time = datetime.now().isoformat()
    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO seen_items (original_id) VALUES (?)
            """,
            (original_id,)
        )

        conn.commit()


    with sqlite3.connect(METADATA_DB) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO document_metadata (paper_id, source_name, paper_retrieval_time) VALUES (?, ?, ?)
            """,
            (
                paper_id,
                source_name,
                retrieval_time
            )
        )

        conn.commit()


def save_pdf_file(paper_id,title,content,source_name):
    safe_source = re.sub(
        r'[\\/*?:"<>|]',
        "",
        source_name
    )

    filepath = DATA_DIR / f"{safe_source}_{paper_id}.pdf"


    try:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        title_style = styles["Title"]
        body_style = styles["BodyText"]

        title_style.alignment = TA_LEFT

        story = []
        story.append(Paragraph(escape(title),title_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Source:</b> {escape(source_name)}",body_style))
        story.append(Spacer(1, 10))

        escaped_content = escape(content)

        paragraphs = escaped_content.split("\n")
        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if not paragraph:
                continue

            story.append(Paragraph(paragraph,body_style))

            story.append(Spacer(1, 8))

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

        if filepath.exists():
            try:
                filepath.unlink()

            except Exception:
                pass

        return False


def process_rss_feed(source_config):
    source_name = source_config["source_name"]
    url = source_config["url"]

    logging.info(f"[{source_name}] Starting RSS fetch...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8-sig", errors="ignore")
        parsed_feed = feedparser.parse(content)
    except Exception:
        try:
            parsed_feed = feedparser.parse(url)
        except Exception as e:
            logging.error(f"[{source_name}] " f"Error parsing feed: {e}")
            return

    if not parsed_feed.entries:
        logging.warning(f"[{source_name}] " f"No entries found.")
        return


    new_items_count = 0
    for entry in parsed_feed.entries:
        original_id = getattr(entry, "guid", getattr(entry, "link", None))

        if not original_id:
            logging.warning(f"[{source_name}] "f"Skipping item without GUID/link.")
            continue

        if is_item_seen(original_id):
            logging.info(
                f"[{source_name}] "
                f"Found already-seen article. "
                f"Stopping feed iteration."
            )
            break

        title = getattr(entry, "title", "No Title")

        description = clean_html(getattr(entry,"description",""))

        paper_id = generate_paper_id(original_id)

        saved = save_pdf_file(paper_id, title, description, source_name)

        if saved:
            mark_item_seen_and_save_metadata(original_id, paper_id, source_name)
            new_items_count += 1

    logging.info(
        f"[{source_name}] "
        f"Finished. "
        f"Added {new_items_count} new articles."
    )


def run_all_scrapers():
    logging.info(
        "\n"
        "Starting multi-source news ingestion\n"
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(RSS_SOURCES)) as executor:
        futures = []
        for source in RSS_SOURCES:
            future = executor.submit(process_rss_feed, source)
            futures.append(future)

        for future in futures:
            try:
                future.result()

            except Exception as e:
                logging.error(f"Worker thread failed: {e}")

    logging.info("All ingestion threads completed\n")


if __name__ == "__main__":
    logging.info("News fetcher started.")

    run_all_scrapers()

    fetch_interval = int(os.getenv("FETCH_INTERVAL_MINUTES", "20"))
    schedule.every(fetch_interval).minutes.do(run_all_scrapers)

    logging.info("Scheduler is active.")

    logging.info(f"Next fetch will happen in {fetch_interval} minutes.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("News fetcher gracefully terminated.")
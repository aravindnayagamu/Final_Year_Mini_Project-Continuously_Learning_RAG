import time
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
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
        "source_name": "Hindu_Chennai",
        "url": "https://www.thehindu.com/news/cities/chennai/feeder/default.rss"
    },
    {
        "source_name": "TOI_Delhi",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms"
    },
    {
        "source_name": "TOI_Bengaluru",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/-2128833038.cms"
    },
    {
        "source_name": "Hindu_TamilNadu",
        "url": "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss"
    },
    {
        "source_name": "NDTV_South",
        "url": "https://feeds.feedburner.com/ndtvnews-south"
    },
    {
        "source_name": "Hindu_India",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss"
    },
    {
        "source_name": "TOI_India",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"
    },
    {
        "source_name": "IE_India",
        "url": "https://indianexpress.com/section/india/feed/"
    },
    {
        "source_name": "PIB_India",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
    },
    {
        "source_name": "BBC_World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "source_name": "Guardian_World",
        "url": "https://www.theguardian.com/world/rss"
    },
    {
        "source_name": "AlJazeera_All",
        "url": "https://www.aljazeera.com/xml/rss/all.xml"
    },
    {
        "source_name": "ESPNcricinfo_Top",
        "url": "https://www.espncricinfo.com/rss/content/story/feeds/0.xml"
    },
    {
        "source_name": "Sportstar_Top",
        "url": "https://sportstar.thehindu.com/feeder/default.rss"
    },
    {
        "source_name": "BBC_Sport",
        "url": "https://feeds.bbci.co.uk/sport/rss.xml"
    },
    {
        "source_name": "TheVerge",
        "url": "https://www.theverge.com/rss/index.xml"
    },
    {
        "source_name": "TechCrunch",
        "url": "https://techcrunch.com/feed/"
    },
    {
        "source_name": "Wired",
        "url": "https://www.wired.com/feed/rss"
    },
    {
        "source_name": "EconomicTimes_Top",
        "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms"
    },
    {
        "source_name": "LiveMint_Top",
        "url": "https://www.livemint.com/rss/news"
    },
    {
        "source_name": "MoneyControl_Top",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml"
    },
    {
        "source_name": "BollywoodHungama",
        "url": "https://www.bollywoodhungama.com/rss/news.xml"
    },
    {
        "source_name": "Variety",
        "url": "https://variety.com/feed/"
    },
    {
        "source_name": "Hindu_Cinema",
        "url": "https://www.thehindu.com/entertainment/movies/feeder/default.rss"
    },
    {
        "source_name": "IE_Political_Pulse",
        "url": "https://indianexpress.com/section/political-pulse/feed/"
    },
    {
        "source_name": "News18_Politics",
        "url": "https://www.news18.com/rss/politics.xml"
    },
    {
        "source_name": "ThePrint_Politics",
        "url": "https://theprint.in/category/politics/feed/"
    },
    {
        "source_name": "NDTV_India",
        "url": "https://feeds.feedburner.com/ndtvnews-india-news"
    },
    {
        "source_name": "Politico_Top",
        "url": "https://rss.politico.com/politics-news.xml"
    },
    {
        "source_name": "BBC_Politics",
        "url": "https://feeds.bbci.co.uk/news/politics/rss.xml"
    },
    {
        "source_name": "Guardian_Politics",
        "url": "https://www.theguardian.com/politics/rss"
    },
    {
        "source_name": "ABPLive_Entertainment",
        "url": "https://news.abplive.com/entertainment/feed"
    }
]


_seen_cache = set()


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


def init_databases():
    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (original_id TEXT PRIMARY KEY)
        """)

        conn.commit()

        cursor.execute("SELECT original_id FROM seen_items")
        for row in cursor.fetchall():
            _seen_cache.add(row[0])

    pg_conn = _get_pg_conn()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute("SELECT paper_id FROM documents")
                for row in cur.fetchall():
                    _seen_cache.add(row[0])
        except Exception:
            pass
        finally:
            pg_conn.close()

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
    return original_id in _seen_cache


def mark_item_seen_and_save_metadata(original_id, paper_id, source_name, title=None, file_name=None):
    _seen_cache.add(original_id)
    retrieval_dt = datetime.now()
    retrieval_iso = retrieval_dt.isoformat()
    if not file_name:
        safe_source = re.sub(r'[\\/*?:"<>|]', "", source_name)
        file_name = f"{safe_source}_{paper_id}.pdf"

    with sqlite3.connect(TRACKER_DB) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO seen_items (original_id) VALUES (?)
            """,
            (original_id,)
        )

        conn.commit()

    pg_conn = _get_pg_conn()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (paper_id, source_name, title, retrieval_time, file_name, vectorization_status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (paper_id) DO NOTHING
                    """,
                    (paper_id, source_name, title, retrieval_dt, file_name)
                )
            pg_conn.commit()
        except Exception:
            pass
        finally:
            pg_conn.close()

    with sqlite3.connect(METADATA_DB) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO document_metadata (paper_id, source_name, paper_retrieval_time) VALUES (?, ?, ?)
            """,
            (
                paper_id,
                source_name,
                retrieval_iso
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
        with urllib.request.urlopen(req, timeout=8) as resp:
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
    for entry in parsed_feed.entries[:10]:
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
            safe_source = re.sub(r'[\\/*?:"<>|]', "", source_name)
            pdf_name = f"{safe_source}_{paper_id}.pdf"
            mark_item_seen_and_save_metadata(original_id, paper_id, source_name, title=title, file_name=pdf_name)
            new_items_count += 1

    logging.info(
        f"[{source_name}] "
        f"Finished. "
        f"Added {new_items_count} new articles."
    )


def run_all_scrapers(timeout=None):
    logging.info(
        "\n"
        "Starting multi-source news ingestion\n"
    )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(24, len(RSS_SOURCES)))
    futures = [executor.submit(process_rss_feed, source) for source in RSS_SOURCES]

    done, not_done = concurrent.futures.wait(futures, timeout=timeout)

    for future in done:
        try:
            future.result()

        except Exception as e:
            logging.error(f"Worker thread failed: {e}")

    if not_done:
        logging.warning(f"Fetch time budget reached; abandoning {len(not_done)} unfinished feeds")

    executor.shutdown(wait=False, cancel_futures=True)

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
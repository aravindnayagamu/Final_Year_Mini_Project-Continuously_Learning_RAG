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
        "source_name": "TOI_India",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"
    },
    {
        "source_name": "TOI_World",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/296589292.cms"
    },
    {
        "source_name": "TOI_Business",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/1898055.cms"
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
        "source_name": "TOI_Tech",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/66949542.cms"
    },
    {
        "source_name": "TOI_Entertainment",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/1081479906.cms"
    },
    {
        "source_name": "TOI_Chennai",
        "url": "http://timesofindia.indiatimes.com/rssfeeds/2950623.cms"
    },
    {
        "source_name": "NDTV_Top_Stories",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories"
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
        "source_name": "NDTV_South",
        "url": "https://feeds.feedburner.com/ndtvnews-south"
    },
    {
        "source_name": "PIB_India",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
    },
    {
        "source_name": "Hindu_India",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss"
    },
    {
        "source_name": "Hindu_World",
        "url": "https://www.thehindu.com/news/international/feeder/default.rss"
    },
    {
        "source_name": "Hindu_Business",
        "url": "https://www.thehindu.com/business/feeder/default.rss"
    },
    {
        "source_name": "Hindu_Sport",
        "url": "https://www.thehindu.com/sport/feeder/default.rss"
    },
    {
        "source_name": "Hindu_Movies",
        "url": "https://www.thehindu.com/entertainment/movies/feeder/default.rss"
    },
    {
        "source_name": "Hindu_TamilNadu",
        "url": "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss"
    },
    {
        "source_name": "Hindu_Chennai",
        "url": "https://www.thehindu.com/news/cities/chennai/feeder/default.rss"
    },
    {
        "source_name": "IE_India",
        "url": "https://indianexpress.com/section/india/feed/"
    },
    {
        "source_name": "IE_World",
        "url": "https://indianexpress.com/section/world/feed/"
    },
    {
        "source_name": "IE_Business",
        "url": "https://indianexpress.com/section/business/feed/"
    },
    {
        "source_name": "IE_Sports",
        "url": "https://indianexpress.com/section/sports/feed/"
    },
    {
        "source_name": "IE_Tamil_Cinema",
        "url": "https://indianexpress.com/section/entertainment/tamil/feed/"
    },
    {
        "source_name": "IE_Political",
        "url": "https://indianexpress.com/section/political-pulse/feed/"
    },
    {
        "source_name": "IE_Chennai",
        "url": "https://indianexpress.com/section/cities/chennai/feed/"
    },
    {
        "source_name": "HT_India",
        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    },
    {
        "source_name": "HT_World",
        "url": "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml"
    },
    {
        "source_name": "HT_Business",
        "url": "https://www.hindustantimes.com/feeds/rss/business/rssfeed.xml"
    },
    {
        "source_name": "HT_Cricket",
        "url": "https://www.hindustantimes.com/feeds/rss/cricket/rssfeed.xml"
    },
    {
        "source_name": "HT_Cinema",
        "url": "https://www.hindustantimes.com/feeds/rss/entertainment/tamil-cinema/rssfeed.xml"
    },
    {
        "source_name": "IndiaToday_India",
        "url": "https://www.indiatoday.in/rss/1206578"
    },
    {
        "source_name": "IndiaToday_World",
        "url": "https://www.indiatoday.in/rss/1206577"
    },
    {
        "source_name": "IndiaToday_Business",
        "url": "https://www.indiatoday.in/rss/1206513"
    },
    {
        "source_name": "IndiaToday_Sports",
        "url": "https://www.indiatoday.in/rss/1206550"
    },
    {
        "source_name": "IndiaToday_Politics",
        "url": "https://www.indiatoday.in/rss/1206575"
    },
    {
        "source_name": "News18_Top",
        "url": "https://www.news18.com/commonfeeds/v1/eng/rss/india.xml"
    },
    {
        "source_name": "News18_World",
        "url": "https://www.news18.com/commonfeeds/v1/eng/rss/world.xml"
    },
    {
        "source_name": "News18_Business",
        "url": "https://www.news18.com/commonfeeds/v1/eng/rss/business.xml"
    },
    {
        "source_name": "News18_Sports",
        "url": "https://www.news18.com/commonfeeds/v1/eng/rss/sports.xml"
    },
    {
        "source_name": "News18_Tamil",
        "url": "https://tamil.news18.com/commonfeeds/v1/tam/rss/tamil-nadu.xml"
    },
    {
        "source_name": "News18_Tamil_Cinema",
        "url": "https://tamil.news18.com/commonfeeds/v1/tam/rss/entertainment.xml"
    },
    {
        "source_name": "Firstpost_Top",
        "url": "https://www.firstpost.com/commonfeeds/v1/mfp/rss/india.xml"
    },
    {
        "source_name": "Firstpost_Entertainment",
        "url": "https://www.firstpost.com/commonfeeds/v1/mfp/rss/entertainment.xml"
    },
    {
        "source_name": "Scroll_Top",
        "url": "https://feeds.feedburner.com/ScrollinArticles.rss"
    },
    {
        "source_name": "DeccanChronicle_Top",
        "url": "https://www.deccanchronicle.com/rss_feed/"
    },
    {
        "source_name": "LiveMint_Top",
        "url": "https://www.livemint.com/rss/news"
    },
    {
        "source_name": "LiveMint_Markets",
        "url": "https://www.livemint.com/rss/markets"
    },
    {
        "source_name": "EconomicTimes_Top",
        "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms"
    },
    {
        "source_name": "EconomicTimes_Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
    },
    {
        "source_name": "EconomicTimes_Economy",
        "url": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"
    },
    {
        "source_name": "BusinessStandard_Top",
        "url": "https://www.business-standard.com/rss/home_page_top_stories.rss"
    },
    {
        "source_name": "BusinessStandard_Markets",
        "url": "https://www.business-standard.com/rss/markets-106.rss"
    },
    {
        "source_name": "MoneyControl_Top",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml"
    },
    {
        "source_name": "MoneyControl_Markets",
        "url": "https://www.moneycontrol.com/rss/marketreports.xml"
    },
    {
        "source_name": "ABPLive_Top",
        "url": "https://news.abplive.com/home/feed"
    },
    {
        "source_name": "ABPLive_Entertainment",
        "url": "https://news.abplive.com/entertainment/feed"
    },
    {
        "source_name": "ABPLive_Sports",
        "url": "https://news.abplive.com/sports/feed"
    },
    {
        "source_name": "OneIndia_Top",
        "url": "https://www.oneindia.com/rss/news-fb.xml"
    },
    {
        "source_name": "OneIndia_Tamil",
        "url": "https://tamil.oneindia.com/rss/tamil-news-fb.xml"
    },
    {
        "source_name": "BollywoodHungama",
        "url": "https://www.bollywoodhungama.com/rss/news.xml"
    },
    {
        "source_name": "Vikatan_Cinema",
        "url": "https://www.vikatan.com/api/v1/collections/cinema.rss"
    },
    {
        "source_name": "Vikatan_Top",
        "url": "https://www.vikatan.com/api/v1/collections/latest-news.rss"
    },
    {
        "source_name": "TamilHindu",
        "url": "https://www.hindutamil.in/feed"
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
        "source_name": "Sportstar_Football",
        "url": "https://sportstar.thehindu.com/football/feeder/default.rss"
    },
    {
        "source_name": "BBC_Sport",
        "url": "https://feeds.bbci.co.uk/sport/rss.xml"
    },
    {
        "source_name": "BBC_Cricket",
        "url": "https://feeds.bbci.co.uk/sport/cricket/rss.xml"
    },
    {
        "source_name": "BBC_Top",
        "url": "https://feeds.bbci.co.uk/news/rss.xml"
    },
    {
        "source_name": "BBC_World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "source_name": "BBC_India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
    },
    {
        "source_name": "BBC_Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml"
    },
    {
        "source_name": "BBC_Tech",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"
    },
    {
        "source_name": "BBC_Entertainment",
        "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"
    },
    {
        "source_name": "AlJazeera_All",
        "url": "https://www.aljazeera.com/xml/rss/all.xml"
    },
    {
        "source_name": "Guardian_World",
        "url": "https://www.theguardian.com/world/rss"
    },
    {
        "source_name": "Guardian_India",
        "url": "https://www.theguardian.com/world/india/rss"
    },
    {
        "source_name": "Guardian_Business",
        "url": "https://www.theguardian.com/uk/business/rss"
    },
    {
        "source_name": "Guardian_Sport",
        "url": "https://www.theguardian.com/uk/sport/rss"
    },
    {
        "source_name": "NYT_World",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    },
    {
        "source_name": "NYT_Business",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"
    },
    {
        "source_name": "NYT_Tech",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
    },
    {
        "source_name": "NYT_Arts",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml"
    },
    {
        "source_name": "CNN_Top",
        "url": "http://rss.cnn.com/rss/edition.rss"
    },
    {
        "source_name": "CNN_Business",
        "url": "http://rss.cnn.com/rss/money_latest.rss"
    },
    {
        "source_name": "CNN_Entertainment",
        "url": "http://rss.cnn.com/rss/edition_entertainment.rss"
    },
    {
        "source_name": "DW_Top",
        "url": "https://rss.dw.com/rdf/rss-en-all"
    },
    {
        "source_name": "France24_Top",
        "url": "https://www.france24.com/en/rss"
    },
    {
        "source_name": "SkyNews_World",
        "url": "https://feeds.skynews.com/feeds/rss/world.xml"
    },
    {
        "source_name": "NPR_News",
        "url": "https://feeds.npr.org/1001/rss.xml"
    },
    {
        "source_name": "NPR_World",
        "url": "https://feeds.npr.org/1004/rss.xml"
    },
    {
        "source_name": "CNBC_Top",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    },
    {
        "source_name": "CNBC_Markets",
        "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"
    },
    {
        "source_name": "WSJ_World",
        "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"
    },
    {
        "source_name": "WSJ_Markets",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    },
    {
        "source_name": "Bloomberg_Markets",
        "url": "https://feeds.bloomberg.com/markets/news.rss"
    },
    {
        "source_name": "Economist_World",
        "url": "https://www.economist.com/the-world-this-week/rss.xml"
    },
    {
        "source_name": "StraitsTimes_Asia",
        "url": "https://www.straitstimes.com/news/asia/rss.xml"
    },
    {
        "source_name": "ChannelNewsAsia",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"
    },
    {
        "source_name": "ScmpAsia",
        "url": "https://www.scmp.com/rss/91/feed"
    },
    {
        "source_name": "Dawn_Top",
        "url": "https://www.dawn.com/feeds/home"
    },
    {
        "source_name": "TheDiplomat_SouthAsia",
        "url": "https://thediplomat.com/regions/south-asia/feed/"
    },
    {
        "source_name": "Variety",
        "url": "https://variety.com/feed/"
    },
    {
        "source_name": "HollywoodReporter",
        "url": "https://www.hollywoodreporter.com/feed/"
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
        "source_name": "ArsTechnica",
        "url": "https://feeds.arstechnica.com/arstechnica/index"
    },
    {
        "source_name": "YourStory",
        "url": "https://yourstory.com/feed"
    },
    {
        "source_name": "ScienceDaily",
        "url": "https://www.sciencedaily.com/rss/all.xml"
    },
    {
        "source_name": "NASA",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss"
    },
    {
        "source_name": "WHO_News",
        "url": "https://www.who.int/rss-feeds/news-english.xml"
    },
    {
        "source_name": "RBI_PressReleases",
        "url": "https://rbi.org.in/pressreleases_rss.xml"
    },
    {
        "source_name": "SEBI",
        "url": "https://www.sebi.gov.in/sebirss.xml"
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(24, len(RSS_SOURCES))) as executor:
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
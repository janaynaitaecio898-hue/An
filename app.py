import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen
from xml.etree import ElementTree as ET

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")
FETCH_INTERVAL_SECONDS = 24 * 60 * 60
FEEDS = {
    "全球": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "欧洲": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "亚洲": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "非洲": "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "美洲": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_at TEXT,
            summary TEXT,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def parse_rss_items(xml_data: bytes, source: str):
    root = ET.fromstring(xml_data)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "未命名新闻").strip()
        url = (item.findtext("link") or "").strip()
        summary = (item.findtext("description") or "").strip()
        published_text = (item.findtext("pubDate") or "").strip()

        published_at = None
        if published_text:
            try:
                published_at = parsedate_to_datetime(published_text).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                published_at = None

        if url:
            items.append({
                "source": source,
                "title": title,
                "url": url,
                "summary": summary,
                "published_at": published_at,
            })
    return items


def save_articles(region: str, articles: list[dict]):
    if not articles:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    inserted = 0
    for article in articles:
        try:
            conn.execute(
                "INSERT INTO articles (region, source, title, url, published_at, summary, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (region, article["source"], article["title"], article["url"], article["published_at"], article["summary"], now),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    return inserted


def fetch_region_feed(region: str, feed_url: str):
    try:
        with urlopen(feed_url, timeout=20) as response:
            xml_data = response.read()
    except URLError:
        return 0
    articles = parse_rss_items(xml_data, source=feed_url)
    return save_articles(region, articles)


def fetch_global_news_once():
    return sum(fetch_region_feed(region, url) for region, url in FEEDS.items())


def cleanup_old_articles(days=14):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conn = get_db_connection()
    conn.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff.isoformat(),))
    conn.commit()
    conn.close()


def background_scheduler():
    while True:
        fetch_global_news_once()
        cleanup_old_articles()
        time.sleep(FETCH_INTERVAL_SECONDS)


def list_articles(limit=200):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT region, source, title, url, published_at, summary, fetched_at FROM articles ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_region_counts():
    conn = get_db_connection()
    rows = conn.execute("SELECT region, COUNT(*) AS total FROM articles GROUP BY region ORDER BY total DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_fetch():
    conn = get_db_connection()
    row = conn.execute("SELECT MAX(fetched_at) AS last_fetch FROM articles").fetchone()
    conn.close()
    return row["last_fetch"] if row else None


def render_home_page():
    articles = list_articles()
    region_counts = list_region_counts()
    last_fetch = get_last_fetch() or "尚未抓取到数据"

    badges = "".join([f'<span class="badge">{r["region"]}：{r["total"]}</span>' for r in region_counts])
    if not badges:
        badges = "<span class=\"badge\">暂无统计数据</span>"

    cards = []
    for article in articles:
        cards.append(
            f"""
            <article class=\"card\"> 
              <h2><a href=\"{article['url']}\" target=\"_blank\" rel=\"noopener noreferrer\">{article['title']}</a></h2>
              <p class=\"meta\"><strong>{article['region']}</strong> · 发布时间：{article['published_at'] or '未知'} · 来源：{article['source']}</p>
              <p>{article['summary']}</p>
            </article>
            """
        )

    if not cards:
        cards_html = "<p>暂时没有新闻数据，点击“立即刷新”尝试抓取。</p>"
    else:
        cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>全球信息日报</title>
    <link rel=\"stylesheet\" href=\"/static/style.css\" />
  </head>
  <body>
    <header>
      <h1>🌍 全球信息日报</h1>
      <p>每天自动搜集全球重点信息，按地区快速浏览。</p>
      <div class=\"actions\">
        <form action=\"/refresh\" method=\"post\"><button type=\"submit\">立即刷新</button></form>
        <small>最近抓取时间：{last_fetch}</small>
      </div>
    </header>
    <section class=\"stats\">{badges}</section>
    <main>{cards_html}</main>
  </body>
</html>"""


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            content = render_home_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path == "/api/articles":
            payload = json.dumps(list_articles(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == "/static/style.css":
            css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
            if not os.path.exists(css_path):
                self.send_error(404, "Not Found")
                return
            with open(css_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/refresh":
            fetch_global_news_once()
            cleanup_old_articles()
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        self.send_error(404, "Not Found")


def run_server(host="0.0.0.0", port=8000):
    init_db()
    fetch_global_news_once()
    worker = threading.Thread(target=background_scheduler, daemon=True)
    worker.start()

    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"Server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

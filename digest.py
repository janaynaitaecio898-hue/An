#!/usr/bin/env python3
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, List
from urllib.parse import quote_plus

import feedparser
import requests
from dotenv import load_dotenv


@dataclass
class Item:
    source: str
    title: str
    url: str
    published: datetime
    summary: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dt(dt_struct) -> datetime:
    if not dt_struct:
        return _utc_now()
    try:
        return datetime(*dt_struct[:6], tzinfo=timezone.utc)
    except Exception:
        return _utc_now()


def fetch_google_news(keyword: str, limit: int) -> List[Item]:
    q = quote_plus(keyword)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    items: List[Item] = []
    for e in feed.entries[:limit]:
        items.append(
            Item(
                source=f"Google News / {keyword}",
                title=e.get("title", "(no title)"),
                url=e.get("link", ""),
                published=_safe_dt(e.get("published_parsed")),
                summary=e.get("summary", ""),
            )
        )
    return items


def fetch_hn(keyword: str, limit: int) -> List[Item]:
    url = "https://hn.algolia.com/api/v1/search"
    r = requests.get(url, params={"query": keyword, "tags": "story", "hitsPerPage": limit}, timeout=20)
    r.raise_for_status()
    data = r.json()
    items: List[Item] = []
    for h in data.get("hits", []):
        published = _utc_now()
        created_at = h.get("created_at")
        if created_at:
            try:
                published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                pass
        items.append(
            Item(
                source=f"Hacker News / {keyword}",
                title=h.get("title") or h.get("story_title") or "(no title)",
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                published=published,
                summary=h.get("_highlightResult", {}).get("title", {}).get("value", ""),
            )
        )
    return items


def fetch_github(keyword: str, limit: int) -> List[Item]:
    url = "https://api.github.com/search/repositories"
    r = requests.get(url, params={"q": keyword, "sort": "updated", "order": "desc", "per_page": limit}, timeout=20)
    r.raise_for_status()
    data = r.json()
    items: List[Item] = []
    for repo in data.get("items", []):
        updated = repo.get("updated_at")
        published = _utc_now()
        if updated:
            try:
                published = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except ValueError:
                pass
        items.append(
            Item(
                source=f"GitHub Repos / {keyword}",
                title=repo.get("full_name", "(no title)"),
                url=repo.get("html_url", ""),
                published=published,
                summary=repo.get("description") or "",
            )
        )
    return items


def dedupe(items: Iterable[Item]) -> List[Item]:
    seen = set()
    out = []
    for i in items:
        key = i.url.strip() or i.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


def build_html(items: List[Item]) -> str:
    rows = []
    for i in items:
        ts = i.published.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        rows.append(
            f"<li><b>{i.title}</b><br>"
            f"<small>{i.source} | {ts}</small><br>"
            f"<a href='{i.url}'>{i.url}</a><br>"
            f"<small>{i.summary}</small></li><br>"
        )
    return (
        "<h2>Daily CloudCode/Codex Digest</h2>"
        "<p>自动抓取最新技巧、进展和新闻：</p>"
        f"<ul>{''.join(rows)}</ul>"
    )


def send_email(subject: str, html: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    pwd = os.environ["SMTP_PASS"]
    sender = os.environ["EMAIL_FROM"]
    receiver = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, pwd)
        server.sendmail(sender, [receiver], msg.as_string())


def main() -> None:
    load_dotenv()

    keywords = [k.strip() for k in os.getenv("KEYWORDS", "cloud code,codex,claude code").split(",") if k.strip()]
    limit = int(os.getenv("MAX_ITEMS_PER_SOURCE", "8"))

    all_items: List[Item] = []
    for kw in keywords:
        all_items.extend(fetch_google_news(kw, limit))
        all_items.extend(fetch_hn(kw, limit))
        all_items.extend(fetch_github(kw, limit))

    all_items = dedupe(all_items)
    all_items.sort(key=lambda x: x.published, reverse=True)
    top_items = all_items[:60]

    if not top_items:
        print("No items found.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[Daily Digest] CloudCode/Codex updates - {today}"
    html = build_html(top_items)
    send_email(subject, html)
    print(f"Sent {len(top_items)} items.")


if __name__ == "__main__":
    main()

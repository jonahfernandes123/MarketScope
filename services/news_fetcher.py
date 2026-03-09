from __future__ import annotations

import html as html_lib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    yf = None
    _YF_AVAILABLE = False

from models.instruments import CONTEXT_QUERIES, INSTRUMENT_MAP


# ── Yahoo Finance news ───────────────────────────────────────────────────────────

def _parse_yf_news_item(item: dict) -> dict | None:
    """Parse a yfinance news item — handles both old and new API formats."""
    try:
        content = item.get("content", {})
        if content:
            # New yfinance format (0.2.28+)
            title = (content.get("title") or "").strip()
            summary = (content.get("summary") or content.get("description") or "").strip()
            canonical = content.get("canonicalUrl", {})
            url = (canonical.get("url") if isinstance(canonical, dict) else "") or ""
            provider = content.get("provider", {})
            publisher = (provider.get("displayName") if isinstance(provider, dict) else "") or ""
            pub_raw = content.get("pubDate", "")
            try:
                dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                published = dt.strftime("%b %d, %Y")
            except Exception:
                published = pub_raw[:10] if pub_raw else ""
        else:
            # Old yfinance format
            title = (item.get("title") or "").strip()
            summary = (item.get("summary") or "").strip()
            url = item.get("link") or ""
            publisher = item.get("publisher") or ""
            ts = item.get("providerPublishTime") or 0
            published = datetime.utcfromtimestamp(ts).strftime("%b %d, %Y") if ts else ""

        if not title or not url:
            return None
        if len(summary) > 260:
            summary = summary[:260].rstrip() + "\u2026"
        return {"title": title, "summary": summary, "url": url,
                "publisher": publisher, "published": published}
    except Exception:
        return None


def _fetch_yf_news(ticker_sym: str) -> list[dict]:
    """Return up to 3 parsed news items from yfinance for the given ticker."""
    try:
        raw = yf.Ticker(ticker_sym).news or []
        parsed = [p for item in raw[:8] if (p := _parse_yf_news_item(item))]
        return parsed[:3]
    except Exception:
        return []


# ── Google News RSS ──────────────────────────────────────────────────────────────

def _fetch_news_for_query(query: str) -> list[dict]:
    """Fetch live news from Google News RSS for a raw query string."""
    query_enc = query.replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={query_enc}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MarketSnapshot/1.0)"})
        with urlopen(req, timeout=7) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = root.findall(".//item")[:8]
        results = []
        for item in items:
            title_el   = item.find("title")
            link_el    = item.find("link")
            guid_el    = item.find("guid")
            pubdate_el = item.find("pubDate")
            if title_el is None:
                continue
            title = html_lib.unescape(title_el.text or "").strip()
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0].strip(), parts[1].strip()
            link = ""
            if link_el is not None and link_el.text:
                link = link_el.text.strip()
            if not link and guid_el is not None and guid_el.text:
                link = guid_el.text.strip()
            pub_str = ""
            if pubdate_el is not None and pubdate_el.text:
                try:
                    dt = parsedate_to_datetime(pubdate_el.text)
                    pub_str = dt.strftime("%b %d, %Y")
                except Exception:
                    pub_str = (pubdate_el.text or "")[:16]
            if title:
                results.append({"title": title, "url": link or "#",
                                 "published": pub_str, "source": source})
        return results
    except Exception:
        return []


def _fetch_context_news(key: str) -> list[dict]:
    """Fetch live macro/geopolitical news from Google News RSS."""
    query = CONTEXT_QUERIES.get(key, INSTRUMENT_MAP.get(key, {}).get("label", key))
    return _fetch_news_for_query(query)

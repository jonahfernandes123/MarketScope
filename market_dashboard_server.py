# THIS IS THE ACTIVE MARKET DASHBOARD SERVER
"""
market_snapshot_web.py
----------------------
Web-based market dashboard with interactive charts, live news, and macro analysis.
Runs at http://localhost:5000

Data sources (all free, no API key required):
  - Bitcoin       : CoinGecko public API (price) + yfinance (history)
  - EUR/USD       : Frankfurter.app (price + monthly/yearly history)
  - Gold, Silver, Copper, Brent, Henry Hub, TTF Gas : Yahoo Finance (yfinance)
  - News & Context: Yahoo Finance news + Google News RSS

Requirements:
  pip install flask requests yfinance
"""

from __future__ import annotations

import concurrent.futures
import threading

from flask import Flask, jsonify, redirect, render_template, request as freq

from models.instruments import CONTEXT_QUERIES, INSTRUMENT_MAP, INSTRUMENTS, SUMMARIES
from services.market_data import YFINANCE_AVAILABLE, _history_bitcoin, _history_ethereum, _history_eurusd, _history_yf
from services.news_fetcher import _fetch_context_news, _fetch_yf_news
from services.price_cache import _background_loop, _cache_lock, _price_data, refresh_prices

app = Flask(__name__)
REFRESH_SECONDS = 30


# ── API routes ─────────────────────────────────────────────────────────────────

@app.route("/api/prices")
def api_prices():
    with _cache_lock:
        result = []
        for inst in INSTRUMENTS:
            d = _price_data.get(inst["key"], {})
            result.append({
                "key": inst["key"], "label": inst["label"],
                "price": d.get("price"), "prev_price": d.get("prev_price"),
                "error": d.get("error"),
                "prefix": inst["prefix"], "suffix": inst["suffix"],
                "decimals": inst["decimals"], "thousands": inst["thousands"],
                "icon": inst["icon"], "accent": inst["accent"],
            })
    return jsonify(result)


@app.route("/api/history/<key>")
def api_history(key: str):
    inst = INSTRUMENT_MAP.get(key)
    if not inst:
        return jsonify({"error": "Unknown instrument"}), 404
    range_param = freq.args.get("range", "1mo")
    if range_param not in ("1d", "1w", "1mo", "1y"):
        range_param = "1mo"
    try:
        if key == "bitcoin":
            data = _history_bitcoin(range_param)
        elif key == "ethereum":
            data = _history_ethereum(range_param)
        elif key == "eurusd":
            data = _history_eurusd(range_param)
        elif inst["ticker"]:
            data = _history_yf(inst["ticker"], range_param)
        else:
            return jsonify({"error": "No history source configured"}), 500
        data.update({
            "label": inst["label"], "prefix": inst["prefix"],
            "suffix": inst["suffix"], "decimals": inst["decimals"],
            "thousands": inst["thousands"], "accent": inst["accent"],
        })
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/summary/<key>")
def api_summary(key: str):
    """Return static analysis + live news for one instrument."""
    s = SUMMARIES.get(key)
    if not s:
        return jsonify({"error": "No summary available"}), 404

    ticker = INSTRUMENT_MAP.get(key, {}).get("ticker", "")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_articles = pool.submit(_fetch_yf_news, ticker) if ticker else None
        f_context  = pool.submit(_fetch_context_news, key)
        articles = f_articles.result() if f_articles else []
        context  = f_context.result()

    return jsonify({
        "overview":     s["overview"],
        "macro":        s["macro"],
        "geopolitical": s["geopolitical"],
        "outlook":      s["outlook"],
        "articles":     articles,
        "context":      context,
    })


# ── Homepage API routes ─────────────────────────────────────────────────────────

@app.route("/api/home/movers")
def api_home_movers():
    """Return all instruments ranked by absolute % change (largest first)."""
    with _cache_lock:
        snapshot = dict(_price_data)

    rows = []
    for inst in INSTRUMENTS:
        d = snapshot.get(inst["key"], {})
        price      = d.get("price")
        prev_price = d.get("prev_price")
        if price is not None and prev_price and prev_price != 0:
            pct = (price - prev_price) / prev_price * 100
        else:
            pct = None
        rows.append({
            "key":      inst["key"],
            "label":    inst["label"],
            "icon":     inst["icon"],
            "accent":   inst["accent"],
            "prefix":   inst["prefix"],
            "suffix":   inst["suffix"],
            "decimals": inst["decimals"],
            "thousands":inst["thousands"],
            "price":    price,
            "pct":      round(pct, 3) if pct is not None else None,
            "error":    d.get("error"),
        })

    rows.sort(key=lambda r: abs(r["pct"]) if r["pct"] is not None else -1, reverse=True)
    return jsonify(rows)


@app.route("/api/home/news")
def api_home_news():
    """Aggregate the latest yfinance news across all instruments in parallel."""
    def _fetch(inst):
        return _fetch_yf_news(inst["ticker"]) if inst.get("ticker") else []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(INSTRUMENTS)) as pool:
        futures = {pool.submit(_fetch, inst): inst for inst in INSTRUMENTS}
        seen_urls = set()
        articles  = []
        for future in concurrent.futures.as_completed(futures):
            for article in (future.result() or [])[:2]:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    inst = futures[future]
                    articles.append({**article, "instrument": inst["label"],
                                     "accent": inst["accent"]})

    articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    return jsonify(articles)


_DRIVERS_QUERY = "global markets economy federal reserve inflation interest rates"

@app.route("/api/home/drivers")
def api_home_drivers():
    """Fetch broad macro/market headlines from Google News RSS."""
    CONTEXT_QUERIES["__drivers__"] = _DRIVERS_QUERY
    results = _fetch_context_news("__drivers__")
    return jsonify(results)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html", refresh_seconds=REFRESH_SECONDS)

@app.route("/dashboard")
def dashboard_redirect():
    return redirect("/", code=301)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not YFINANCE_AVAILABLE:
        print("[WARN] yfinance not installed — commodity prices will fail.")
        print("       Run:  pip install yfinance")

    print(f"Fetching initial prices for {len(INSTRUMENTS)} instruments…")
    refresh_prices()
    print("Done. Starting background refresh thread.\n")

    bg = threading.Thread(target=_background_loop, args=(REFRESH_SECONDS,), daemon=True)
    bg.start()

    print("  Market Snapshot  ·  http://192.168.40.85:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)

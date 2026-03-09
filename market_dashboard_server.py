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
import html as html_lib
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

import requests
from flask import Flask, jsonify, request as freq

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

app = Flask(__name__)
REFRESH_SECONDS = 30


# ── Fetchers ───────────────────────────────────────────────────────────────────

def _get(url, params=None, timeout=12):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_bitcoin():
    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": "bitcoin", "vs_currencies": "usd"},
    )
    price = float(data["bitcoin"]["usd"])
    # Use yfinance previous daily close as comparison basis — consistent with all other instruments
    prev_price = None
    if YFINANCE_AVAILABLE:
        try:
            hist = yf.Ticker("BTC-USD").history(period="5d", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                prev_price = float(closes.iloc[-2])
        except Exception:
            pass
    return price, prev_price


def fetch_eurusd():
    data = _get("https://api.frankfurter.app/latest", params={"from": "EUR", "to": "USD"})
    price = float(data["rates"]["USD"])
    prev_price = None
    if YFINANCE_AVAILABLE:
        try:
            hist = yf.Ticker("EURUSD=X").history(period="5d", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                prev_price = float(closes.iloc[-2])
        except Exception:
            pass
    return price, prev_price


def fetch_yf(ticker: str) -> tuple:
    if not YFINANCE_AVAILABLE:
        raise RuntimeError("yfinance not installed — run: pip install yfinance")
    hist = yf.Ticker(ticker).history(period="5d", interval="1d")
    if hist.empty:
        raise ValueError(f"No data returned for {ticker}")
    closes = hist["Close"].dropna()
    price = float(closes.iloc[-1])
    prev_price = float(closes.iloc[-2]) if len(closes) >= 2 else None
    return price, prev_price


# ── Instrument registry ────────────────────────────────────────────────────────

INSTRUMENTS: list[dict] = [
    {
        "key":       "bitcoin",
        "label":     "Bitcoin",
        "fetch":     fetch_bitcoin,
        "prefix":    "$",
        "suffix":    "",
        "decimals":  2,
        "thousands": True,
        "ticker":    "BTC-USD",
        "icon":      "&#x20BF;",
        "accent":    "#f7931a",
    },
    {
        "key":       "gold",
        "label":     "Gold",
        "fetch":     lambda: fetch_yf("GC=F"),
        "prefix":    "$",
        "suffix":    " /oz",
        "decimals":  2,
        "thousands": True,
        "ticker":    "GC=F",
        "icon":      "&#9670;",
        "accent":    "#f59e0b",
    },
    {
        "key":       "silver",
        "label":     "Silver",
        "fetch":     lambda: fetch_yf("SI=F"),
        "prefix":    "$",
        "suffix":    " /oz",
        "decimals":  3,
        "thousands": False,
        "ticker":    "SI=F",
        "icon":      "&#9671;",
        "accent":    "#94a3b8",
    },
    {
        "key":       "copper",
        "label":     "Copper",
        "fetch":     lambda: fetch_yf("HG=F"),
        "prefix":    "$",
        "suffix":    " /lb",
        "decimals":  4,
        "thousands": False,
        "ticker":    "HG=F",
        "icon":      "&#9679;",
        "accent":    "#c87941",
    },
    {
        "key":       "eurusd",
        "label":     "EUR / USD",
        "fetch":     fetch_eurusd,
        "prefix":    "",
        "suffix":    "",
        "decimals":  4,
        "thousands": False,
        "ticker":    "EURUSD=X",
        "icon":      "&#8364;/$",
        "accent":    "#3b82f6",
    },
    {
        "key":       "brent",
        "label":     "Brent Crude",
        "fetch":     lambda: fetch_yf("BZ=F"),
        "prefix":    "$",
        "suffix":    " /bbl",
        "decimals":  2,
        "thousands": False,
        "ticker":    "BZ=F",
        "icon":      "&#9679;",
        "accent":    "#10b981",
    },
    {
        "key":       "henryhub",
        "label":     "Henry Hub Gas",
        "fetch":     lambda: fetch_yf("NG=F"),
        "prefix":    "$",
        "suffix":    " /MMBtu",
        "decimals":  3,
        "thousands": False,
        "ticker":    "NG=F",
        "icon":      "&#128293;",
        "accent":    "#8b5cf6",
    },
    {
        "key":       "ttfgas",
        "label":     "TTF Gas",
        "fetch":     lambda: fetch_yf("TTF=F"),
        "prefix":    "\u20ac",
        "suffix":    " /MWh",
        "decimals":  2,
        "thousands": False,
        "ticker":    "TTF=F",
        "icon":      "&#9889;",
        "accent":    "#f43f5e",
    },
]

INSTRUMENT_MAP = {i["key"]: i for i in INSTRUMENTS}


# ── Static summaries (overview + outlook stay static; bullets used as fallback) ──

SUMMARIES: dict[str, dict] = {
    "bitcoin": {
        "overview": (
            "Bitcoin is the world's leading digital asset, with a fixed supply cap of 21 million coins. "
            "Its price is driven by institutional adoption cycles, macroeconomic liquidity, and the "
            "four-year halving schedule that periodically cuts new supply issuance in half."
        ),
        "macro": [
            "Spot Bitcoin ETF approvals (Jan 2024) unlocked institutional capital at scale",
            "Fed rate cuts in 2024-25 boosted risk appetite across digital assets",
            "April 2024 halving reduced block reward to 3.125 BTC — historical bull catalyst",
            "US national debt concerns driving 'digital gold' store-of-value narrative",
            "Corporate treasury adoption (MicroStrategy, Tesla) creates structural demand floor",
        ],
        "geopolitical": [
            "Pro-crypto regulatory shift under 2024-25 US administration eased compliance barriers",
            "El Salvador and other nations adopting BTC as legal tender signals sovereign demand",
            "China's mining ban pushed hashrate to US, Canada, and Kazakhstan",
            "Russia and Iran reported use of crypto to circumvent Western financial sanctions",
            "US Bitcoin Strategic Reserve proposal added a new sovereign demand narrative",
        ],
        "outlook": (
            "Bitcoin's medium-term trajectory is tied to global liquidity expansion, ETF inflow momentum, "
            "and the diminishing post-halving supply. Regulatory clarity in the US and Europe remains the "
            "key variable for the next wave of institutional adoption."
        ),
    },
    "gold": {
        "overview": (
            "Gold is the world's premier safe-haven asset and inflation hedge, with a 5,000-year track record "
            "as a store of value. Record central bank purchases since 2022, combined with geopolitical "
            "fragmentation and US fiscal concerns, have supported prices above $2,000/oz structurally."
        ),
        "macro": [
            "Fed rate pivot (2024-25) and dollar weakness are the primary bullish catalysts",
            "US national debt exceeding $35 trillion eroding confidence in USD as reserve asset",
            "Declining real yields increase the relative attractiveness of non-yielding gold",
            "Persistent services inflation sustaining the hedge and safe-haven narrative",
            "Gold ETF inflows and managed money long positioning at multi-year highs",
        ],
        "geopolitical": [
            "Central bank buying at record pace: China, India, Poland, Turkey all major buyers",
            "BRICS nations actively diversifying reserves away from US Treasuries into gold",
            "Russia-Ukraine war and Middle East conflict driving safe-haven premium",
            "Western sanctions on Russia (2022) demonstrated dollar weaponisation risk to EM holders",
            "De-dollarisation trend accelerating non-Western central bank accumulation",
        ],
        "outlook": (
            "Gold's structural bull case rests on central bank reserve diversification, declining real rates, "
            "and persistent geopolitical uncertainty. The key near-term variables are the pace of Fed easing "
            "and whether EM central banks maintain their record purchasing cadence."
        ),
    },
    "silver": {
        "overview": (
            "Silver uniquely straddles the precious metals and industrial commodities markets. "
            "Nearly 60% of demand now comes from industrial applications — with solar photovoltaics, "
            "electric vehicles, and advanced electronics representing the fastest-growing segments "
            "— while investment demand adds a macro overlay."
        ),
        "macro": [
            "Solar panel manufacturing is the fastest-growing silver demand segment globally",
            "Each GW of solar capacity requires ~70 tonnes of silver — IRA and EU Green Deal driving build-out",
            "Gold/silver ratio above 80 historically signals silver is undervalued relative to gold",
            "Physical silver market ran a structural deficit for three consecutive years (2021-23)",
            "Rising industrial demand increasingly offsetting weaker jewellery and coin investment",
        ],
        "geopolitical": [
            "~75% of silver mined as a byproduct of lead, zinc, and copper — supply tied to base metals cycle",
            "Mexico and Peru supply ~40% of global silver — political instability (Peru strikes) a risk",
            "US-China trade tensions affecting solar panel supply chains and silver demand forecasts",
            "Green energy subsidies (US IRA, EU taxonomy) structurally accelerating solar silver demand",
            "Tight LBMA and COMEX warehouse inventories amplify short-term supply squeezes",
        ],
        "outlook": (
            "Silver's dual precious/industrial role makes it a beneficiary of both risk-on (industrial demand) "
            "and risk-off (safe-haven) environments. The energy transition megatrend provides a long-term "
            "structural demand tailwind, while near-term price action continues to shadow gold's moves."
        ),
    },
    "copper": {
        "overview": (
            "Copper, the essential metal of electrification, is critical infrastructure for EVs, "
            "renewable energy, and power grid upgrades. Growing long-term demand against a supply "
            "pipeline constrained by permitting delays, aging mines, and political risk is creating "
            "a structural deficit outlook for the next decade."
        ),
        "macro": [
            "China consumes ~55% of global copper — PMI readings are the key near-term price signal",
            "Each EV requires 4x more copper than an internal-combustion vehicle",
            "Offshore wind turbines require 8-10 tonnes of copper per MW of installed capacity",
            "US and EU grid modernisation programmes require billions of metres of new copper cable",
            "Mine supply growth constrained: average 15-20 year permitting timeline for new projects",
        ],
        "geopolitical": [
            "Chile and Peru supply ~40% of global copper — labour strikes and left-wing policy risk",
            "DRC's Kamoa-Kakula mine is a major new swing producer but faces logistics constraints",
            "US tariffs on Chinese manufactured goods affecting downstream copper product demand",
            "China stimulus packages (property sector, infrastructure) directly drive price spikes",
            "Water scarcity in Chile's Atacama Desert threatens output at major mines long-term",
        ],
        "outlook": (
            "Copper's long-term bull case — driven by global electrification — is structurally sound. "
            "Near-term prices remain hostage to Chinese economic data, but the decade-long supply "
            "deficit thesis is increasingly consensus among major mining houses and investment banks."
        ),
    },
    "eurusd": {
        "overview": (
            "EUR/USD is the world's most traded currency pair, accounting for ~23% of daily FX volume. "
            "It reflects the monetary policy and economic divergence between the Eurozone and the "
            "United States, and serves as a key barometer of global risk appetite and dollar strength."
        ),
        "macro": [
            "ECB vs Fed rate differential: narrowing as both institutions cut through 2024-25",
            "Eurozone manufacturing in prolonged recession, weighing on euro growth fundamentals",
            "US economic exceptionalism — stronger growth and productivity — maintaining dollar demand",
            "ECB quantitative tightening (balance sheet reduction) providing a longer-term euro floor",
            "Euro area services sector showing resilience; PMI divergence vs. industry remains wide",
        ],
        "geopolitical": [
            "Russia-Ukraine war energy impact structurally raised European production costs vs. US",
            "US tariff threats on European auto and industrial exports (2025 trade policy escalation)",
            "French fiscal trajectory and debt-to-GDP ratio weighing on euro area credibility",
            "German industrial competitiveness declining — energy cost disadvantage vs. US and Asia",
            "USD retains global reserve currency status, providing a structural demand floor",
        ],
        "outlook": (
            "EUR/USD near-term direction hinges on the relative pace of Fed versus ECB rate cuts and "
            "whether European growth can recover from its manufacturing slump. US tariff escalation "
            "represents the key downside risk to the euro; any positive Ukraine resolution could "
            "trigger a sharp relief rally."
        ),
    },
    "brent": {
        "overview": (
            "Brent Crude is the global benchmark for oil pricing, covering ~60% of international trade. "
            "Supply decisions from OPEC+, record US shale output, and demand growth from China and India "
            "are the dominant price drivers, while energy transition narratives weigh on the long-term outlook."
        ),
        "macro": [
            "OPEC+ voluntary production cuts supporting price floor, but compliance varies by member",
            "US shale output at record highs (~13 mb/d) is effectively capping prices above $90/bbl",
            "China demand recovery uneven — aviation and transport strong, industrial segment soft",
            "India emerging as the primary demand growth engine, partially replacing slowing China",
            "IEA projects peak oil demand in advanced economies before 2030 — long-term headwind",
        ],
        "geopolitical": [
            "Russia's oil redirected to India and China after G7 price cap and Western sanctions",
            "Middle East conflict (Israel-Gaza, Iran tensions) embeds a risk premium in Brent",
            "Houthi Red Sea attacks forcing shipping route diversions and raising freight costs",
            "Iran sanctions enforcement (variable) affecting ~1-1.5 million bpd of supply",
            "Libya and Nigeria chronic production disruptions add persistent supply-side volatility",
        ],
        "outlook": (
            "Brent is caught between OPEC+ supply discipline providing a floor and rising non-OPEC "
            "production limiting the ceiling. Middle East escalation risk remains the key upside catalyst, "
            "while a deeper-than-expected Chinese slowdown is the primary downside risk."
        ),
    },
    "henryhub": {
        "overview": (
            "Henry Hub is the primary US natural gas pricing benchmark, located in Erath, Louisiana. "
            "Prices reflect the balance between prolific US shale gas production, growing LNG export "
            "volumes, domestic power generation demand, and highly weather-sensitive consumption patterns."
        ),
        "macro": [
            "US dry gas production at record highs (~105 Bcf/day) — Haynesville and Permian leading",
            "LNG export capacity expansion creates a growing arbitrage link to international prices",
            "Power sector gas demand growing as coal retires and gas backs up intermittent renewables",
            "Storage levels vs. the 5-year seasonal average is the key near-term price indicator",
            "Permian Basin associated gas production grows automatically alongside oil output",
        ],
        "geopolitical": [
            "European LNG demand surge post-2022 linked US and EU gas markets structurally",
            "New LNG export terminals (Plaquemines, Golden Pass) increasing export optionality",
            "Mexico pipeline exports expanding, tying US supply to Latin American demand",
            "FERC permitting uncertainty for next-wave LNG projects creating investment caution",
            "Asian LNG demand (Japan, South Korea, China) competing with Europe for US cargoes",
        ],
        "outlook": (
            "Henry Hub prices remain structurally suppressed by abundant US shale supply, but growing "
            "LNG export capacity is gradually tightening the domestic market. Cold winter weather and "
            "LNG terminal outages remain the primary short-term volatility catalysts."
        ),
    },
    "ttfgas": {
        "overview": (
            "TTF (Title Transfer Facility) is Europe's primary natural gas trading hub, based in the "
            "Netherlands. European gas prices are driven by the near-complete loss of Russian pipeline "
            "supply, reliance on LNG imports, seasonal storage dynamics, and renewable intermittency."
        ),
        "macro": [
            "European LNG import infrastructure massively expanded post-2022 crisis (FSRU terminals)",
            "EU storage typically targets 90%+ fill by November — summer/autumn injection season is key",
            "EU ETS carbon pricing (~EUR 60-80/tonne) adds a structural cost floor for gas consumers",
            "Renewable intermittency (wind droughts, low solar in winter) spikes gas demand as backup",
            "Industrial demand destruction during 2022-23 price spike structurally reduced European consumption",
        ],
        "geopolitical": [
            "Russian pipeline gas flows (Nord Stream destroyed, TurkStream reduced) largely eliminated",
            "Norway is now Europe's single largest gas supplier — pipeline integrity is critical",
            "Algeria and Azerbaijan pipeline volumes partially, but not fully, replacing Russian supply",
            "LNG cargo competition: Europe bids against Japan, South Korea, China for spot cargoes",
            "Ukraine transit agreement expiry affecting remaining Russian transit through Eastern Europe",
        ],
        "outlook": (
            "European TTF prices have normalised significantly from the 2022 crisis peaks but remain "
            "structurally above pre-2021 levels. Key risk factors are a cold winter drawing down storage "
            "rapidly, any Norwegian pipeline outage, or LNG supply disruptions — all of which could "
            "trigger sharp price spikes given Europe's reduced buffer capacity."
        ),
    },
}

# Context search queries for Google News RSS (macro + geopolitical)
CONTEXT_QUERIES = {
    "bitcoin":  "bitcoin price market ETF regulation economic",
    "gold":     "gold price market central bank inflation economic",
    "silver":   "silver price market industrial demand supply",
    "copper":   "copper price market China demand supply",
    "eurusd":   "EUR USD euro dollar exchange rate ECB Fed",
    "brent":    "brent crude oil price OPEC energy supply",
    "henryhub": "natural gas price LNG market Henry Hub",
    "ttfgas":   "European TTF gas price energy market supply",
}


# ── Price cache ────────────────────────────────────────────────────────────────

_price_data: dict[str, dict] = {}
_cache_lock = threading.Lock()


def _update_instrument(inst: dict) -> None:
    """Fetch one instrument's price and update the shared cache (thread-safe).

    On success: stores price and previous day's close (prev_price) for 24h change.
    On error:   keeps the last known values so the UI stays populated.
    """
    key = inst["key"]
    try:
        result = inst["fetch"]()
        if isinstance(result, tuple):
            new_price, new_prev = result
        else:
            new_price, new_prev = result, None
        error = None
    except Exception as exc:
        new_price = None
        new_prev  = None
        error = str(exc)[:100]

    with _cache_lock:
        cached = _price_data.get(key, {})
        ts = datetime.now(timezone.utc).isoformat()
        if error is None:
            _price_data[key] = {
                "price":      new_price,
                "prev_price": new_prev if new_prev is not None else cached.get("prev_price"),
                "error":      None,
                "ts":         ts,
            }
        else:
            _price_data[key] = {
                "price":      cached.get("price"),
                "prev_price": cached.get("prev_price"),
                "error":      error,
                "ts":         ts,
            }


def refresh_prices() -> None:
    threads = [threading.Thread(target=_update_instrument, args=(inst,), daemon=True)
               for inst in INSTRUMENTS]
    for t in threads: t.start()
    for t in threads: t.join()


def _background_loop() -> None:
    while True:
        time.sleep(REFRESH_SECONDS)
        refresh_prices()


# ── History fetchers (range-aware) ─────────────────────────────────────────────

# Date format applied to chart labels for each time range
_RANGE_LABEL_FMT = {"1d": "%H:%M", "1mo": "%b %d", "1y": "%b '%y"}

# yfinance period/interval config for each time range
_RANGE_YF_CFG = {
    "1d":  {"period": "1d",  "interval": "5m"},
    "1mo": {"period": "1mo", "interval": "1d"},
    "1y":  {"period": "1y",  "interval": "1wk"},
}


def _fmt_index_labels(index, fmt: str) -> list[str]:
    """Convert a pandas DatetimeIndex to a list of UTC-formatted label strings."""
    labels = []
    for d in index:
        try:
            labels.append(d.astimezone(timezone.utc).strftime(fmt))
        except Exception:
            labels.append(d.strftime(fmt))
    return labels


def _history_bitcoin(range_param: str) -> dict:
    days_map = {"1d": 1, "1mo": 30, "1y": 365}
    days = days_map.get(range_param, 30)
    params: dict = {"vs_currency": "usd", "days": days}
    if days > 1:
        params["interval"] = "daily"
    data = _get(
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        params=params, timeout=15,
    )
    pts = data["prices"]
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")
    labels = [datetime.utcfromtimestamp(p[0] / 1000).strftime(fmt) for p in pts]
    prices = [round(p[1], 2) for p in pts]
    return {"labels": labels, "prices": prices}


def _history_eurusd(range_param: str) -> dict:
    """EUR/USD history.

    1d  — yfinance intraday (Frankfurter.app is daily-only).
    1mo/1y — Frankfurter.app daily series (more reliable for FX).
    """
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")
    if range_param == "1d":
        hist = yf.Ticker("EURUSD=X").history(**_RANGE_YF_CFG["1d"])
        if hist.empty:
            raise ValueError("No intraday EUR/USD data")
        return {
            "labels": _fmt_index_labels(hist.index, fmt),
            "prices": [round(float(v), 6) for v in hist["Close"]],
        }
    else:
        days  = 30 if range_param == "1mo" else 365
        now   = datetime.now(timezone.utc)
        end   = now.strftime("%Y-%m-%d")
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        rates = _get(f"https://api.frankfurter.app/{start}..{end}",
                     params={"from": "EUR", "to": "USD"})["rates"]
        dates = sorted(rates.keys())
        return {
            "labels": [datetime.strptime(d, "%Y-%m-%d").strftime(fmt) for d in dates],
            "prices": [rates[d]["USD"] for d in dates],
        }


def _history_yf(ticker: str, range_param: str) -> dict:
    """Generic yfinance price history for any ticker."""
    cfg  = _RANGE_YF_CFG.get(range_param, _RANGE_YF_CFG["1mo"])
    hist = yf.Ticker(ticker).history(**cfg)
    if hist.empty:
        raise ValueError(f"No history for {ticker}")
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")
    return {
        "labels": _fmt_index_labels(hist.index, fmt),
        "prices": [round(float(v), 6) for v in hist["Close"]],
    }


# ── News fetchers ──────────────────────────────────────────────────────────────

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


def _fetch_context_news(key: str) -> list[dict]:
    """Fetch live macro/geopolitical news from Google News RSS."""
    query = CONTEXT_QUERIES.get(key, INSTRUMENT_MAP.get(key, {}).get("label", key))
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
    if range_param not in ("1d", "1mo", "1y"):
        range_param = "1mo"
    try:
        if key == "bitcoin":
            data = _history_bitcoin(range_param)
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


# ── HTML template ───────────────────────────────────────────────────────────────

COMBINED_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Snapshot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ── Design tokens ───────────────────────────────────────────── */
:root {
  --bg:        #080d18;
  --surface:   #0e1624;
  --raised:    #131e30;
  --hover:     #1a2840;
  --border:    rgba(255,255,255,0.07);
  --border-hi: rgba(255,255,255,0.14);
  --text:      #dde8f8;
  --muted:     #6b7f9e;
  --dim:       #374d68;
  --green:     #22c55e;
  --red:       #ef4444;
}

/* ── Reset ───────────────────────────────────────────────────── */
*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, sans-serif;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

/* ── Hamburger button ────────────────────────────────────────── */
.hamburger-btn {
  background: none; border: none;
  cursor: pointer; padding: 7px 8px;
  display: flex; flex-direction: column;
  gap: 4px; border-radius: 6px;
  transition: background 0.15s;
  flex-shrink: 0;
}
.hamburger-btn:hover { background: var(--raised); }
.hamburger-btn span {
  display: block; width: 18px; height: 2px;
  background: var(--muted); border-radius: 2px;
  transition: background 0.15s;
}
.hamburger-btn:hover span { background: var(--text); }

/* ── Side drawer backdrop ────────────────────────────────────── */
.drawer-backdrop {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  z-index: 100;
  backdrop-filter: blur(2px);
}
.drawer-backdrop.open { display: block; }

/* ── Side drawer ─────────────────────────────────────────────── */
.side-drawer {
  position: fixed; top: 0; left: 0; bottom: 0;
  width: 230px;
  background: var(--surface);
  border-right: 1px solid var(--border-hi);
  z-index: 110;
  transform: translateX(-100%);
  transition: transform 0.25s cubic-bezier(0.25,0.46,0.45,0.94);
  display: flex; flex-direction: column;
}
.side-drawer.open { transform: translateX(0); }

.drawer-header {
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 18px 16px 16px;
  border-bottom: 1px solid var(--border);
}
.drawer-brand {
  display: flex; align-items: center;
  gap: 9px; font-size: 0.88rem; font-weight: 700;
  color: var(--text); letter-spacing: -0.01em;
}
.drawer-close {
  background: none; border: none;
  color: var(--muted); cursor: pointer;
  font-size: 0.9rem; padding: 5px 7px;
  border-radius: 5px; line-height: 1;
  transition: color 0.15s, background 0.15s;
}
.drawer-close:hover { color: var(--text); background: var(--raised); }

.drawer-section-label {
  font-size: 0.58rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--dim); padding: 14px 16px 6px;
}
.drawer-nav {
  padding: 6px 10px;
  display: flex; flex-direction: column; gap: 2px;
}
.drawer-link {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  font-size: 0.82rem; font-weight: 600;
  color: var(--muted); cursor: pointer;
  text-decoration: none; border: 1px solid transparent;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  user-select: none;
}
.drawer-link:hover { background: var(--raised); color: var(--text); }
.drawer-link.active {
  background: var(--raised); color: var(--text);
  border-color: var(--border);
}
.drawer-link-icon {
  font-size: 0.85rem; width: 16px;
  text-align: center; flex-shrink: 0;
}

/* ── Header ──────────────────────────────────────────────────── */
.header {
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 12px 20px 12px 16px;
  border-bottom: 1px solid var(--border);
  background: rgba(8,13,24,0.92);
  backdrop-filter: blur(10px);
  position: sticky; top: 0; z-index: 50;
  gap: 12px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-logo {
  width: 28px; height: 28px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.72rem; font-weight: 700; color: #fff;
  flex-shrink: 0;
}
.header-title { font-size: 0.92rem; font-weight: 700; letter-spacing: -0.01em; }
.header-right {
  display: flex; flex-direction: column;
  align-items: flex-end; gap: 4px;
}
.clock { font-size: 0.7rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.refresh-row { display: flex; align-items: center; gap: 7px; }
.refresh-label { font-size: 0.67rem; color: var(--dim); }
.refresh-label b { color: var(--muted); }
.live-dot {
  display: inline-block; width: 6px; height: 6px;
  border-radius: 50%; background: var(--green);
  animation: blink 2s ease-in-out infinite; flex-shrink: 0;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
.progress-track { width: 72px; height: 2px; background: var(--border); border-radius: 2px; overflow: hidden; }
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: 2px; transition: width 1s linear;
}

/* ── View system ─────────────────────────────────────────────── */
.view { display: none; }
.view.active { display: block; }

/* ── Page layout ─────────────────────────────────────────────── */
.page { padding: 32px 28px 56px; max-width: 1380px; margin: 0 auto; }
.page-title {
  font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em;
  margin-bottom: 4px;
}
.page-subtitle { font-size: 0.82rem; color: var(--muted); margin-bottom: 32px; }
.section-label {
  font-size: 0.62rem; font-weight: 600;
  letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--dim); margin-bottom: 14px;
  display: flex; align-items: center; gap: 10px;
}
.section-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }

/* ── Briefing card grid ──────────────────────────────────────── */
.briefing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  margin-bottom: 40px;
}

/* ── Briefing card ───────────────────────────────────────────── */
.bcard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 18px 16px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease,
              border-color 0.18s ease, background 0.18s ease;
  position: relative;
  overflow: hidden;
  user-select: none;
  min-height: 160px;
  display: flex;
  flex-direction: column;
}
.bcard-accent {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  border-radius: 14px 14px 0 0;
  background: var(--accent, #3b82f6);
  opacity: 0.55;
  transition: opacity 0.18s;
}
.bcard:hover .bcard-accent { opacity: 1; }
.bcard:hover {
  background: var(--raised);
  border-color: var(--accent, #3b82f6);
  transform: translateY(-3px);
  box-shadow: 0 12px 30px rgba(0,0,0,0.35), 0 0 0 1px var(--accent, #3b82f6);
}
.bcard:active { transform: translateY(-1px); }
.bcard-tag {
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent, #3b82f6);
  margin-bottom: 8px;
}
.bcard-title {
  font-size: 1rem; font-weight: 700;
  letter-spacing: -0.01em;
  margin-bottom: 10px;
}
.bcard-body {
  font-size: 0.78rem; color: var(--muted);
  line-height: 1.6; flex: 1;
}
.bcard-preview-list { list-style: none; padding: 0; }
.bcard-preview-list li {
  font-size: 0.76rem; color: var(--muted);
  padding: 4px 0 4px 14px;
  position: relative;
  border-bottom: 1px solid var(--border);
  line-height: 1.45;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bcard-preview-list li:last-child { border-bottom: none; }
.bcard-preview-list li::before {
  content: '›'; position: absolute; left: 0;
  color: var(--accent, #3b82f6);
}
.bcard-footer {
  margin-top: 12px;
  font-size: 0.65rem; color: var(--dim);
  display: flex; align-items: center; justify-content: space-between;
}
.bcard-cta { color: var(--accent, #3b82f6); font-weight: 600; }

/* Mover chips */
.mover-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.76rem;
}
.mover-row:last-child { border-bottom: none; }
.mover-name { color: var(--text); font-weight: 500; }
.mover-pct  { font-weight: 700; font-variant-numeric: tabular-nums; }
.up   { color: var(--green); }
.down { color: var(--red); }
.neu  { color: var(--dim); }

/* Spinner */
.spin {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid var(--border); border-top-color: var(--muted);
  border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.placeholder {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; color: var(--muted); font-size: 0.8rem; padding: 24px;
}

/* ── Price cards grid ────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px;
  margin-bottom: 32px;
}
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 18px 16px 14px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
  position: relative; overflow: hidden; user-select: none;
}
.card-accent {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  border-radius: 14px 14px 0 0;
  background: var(--accent, #3b82f6); opacity: 0.55; transition: opacity 0.18s;
}
.card:hover .card-accent { opacity: 1; }
.card:hover {
  background: var(--raised); border-color: var(--accent, #3b82f6);
  transform: translateY(-3px);
  box-shadow: 0 12px 30px rgba(0,0,0,0.35), 0 0 0 1px var(--accent, #3b82f6);
}
.card:active { transform: translateY(-1px); }
.card-icon  { font-size: 0.72rem; color: var(--muted); font-weight: 600; letter-spacing: 0.04em; margin-bottom: 8px; }
.card-name  { font-size: 0.68rem; font-weight: 600; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }
.card-price { font-size: 1.35rem; font-weight: 700; color: var(--text); line-height: 1.15; margin-bottom: 8px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; min-height: 1.6rem; }
.card-price.loading { font-size: 0.8rem; color: var(--dim); font-weight: 400; }
.card-price.err     { font-size: 0.68rem; color: var(--red); font-weight: 400; }
.card-change { display: flex; align-items: center; gap: 5px; font-size: 0.8rem; font-weight: 600; }
.card-hint { position: absolute; bottom: 10px; right: 12px; font-size: 0.58rem; font-weight: 500; color: var(--dim); opacity: 0; transition: opacity 0.18s; letter-spacing: 0.04em; }
.card:hover .card-hint { opacity: 1; }

/* ── Modal overlay ───────────────────────────────────────────── */
.overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.78);
  backdrop-filter: blur(6px);
  z-index: 200;
  align-items: flex-start; justify-content: center;
  padding: 20px; overflow-y: auto;
}
.overlay.open { display: flex; }
.modal {
  background: var(--surface);
  border: 1px solid var(--border-hi);
  border-top: 2px solid var(--modal-accent, #3b82f6);
  border-radius: 16px;
  width: 100%; max-width: 860px;
  padding: 28px 30px 32px;
  position: relative;
  animation: fadeUp 0.22s ease;
  margin: auto;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.modal-close {
  position: absolute; top: 14px; right: 16px;
  background: var(--raised); border: 1px solid var(--border);
  color: var(--muted); cursor: pointer;
  font-size: 0.72rem; font-weight: 600; font-family: inherit;
  padding: 5px 12px; border-radius: 6px;
  transition: border-color 0.15s, color 0.15s;
  letter-spacing: 0.04em;
}
.modal-close:hover { color: var(--text); border-color: var(--border-hi); }
.modal-title {
  font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em;
  margin-bottom: 4px; padding-right: 80px;
}
.modal-subtitle { font-size: 0.78rem; color: var(--muted); margin-bottom: 22px; }
.modal-divider { height: 1px; background: var(--border); margin: 0 0 20px; }

/* News list inside briefing modals */
.news-list { list-style: none; padding: 0; margin-bottom: 10px; }
.news-list li {
  padding: 8px 0 8px 16px;
  position: relative;
  border-bottom: 1px solid var(--border);
}
.news-list li:last-child { border-bottom: none; }
.news-list li::before {
  content: '›'; position: absolute; left: 0;
  color: var(--modal-accent, #3b82f6); font-size: 1rem; line-height: 1.5;
}
.news-list a {
  font-size: 0.82rem; color: var(--text); text-decoration: none;
  line-height: 1.5; display: block; transition: color 0.12s;
}
.news-list a:hover { color: var(--modal-accent, #3b82f6); }
.news-meta { font-size: 0.62rem; color: var(--dim); margin-top: 2px; }

/* Movers table in briefing modal */
.movers-table { width: 100%; border-collapse: collapse; }
.movers-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
}
.movers-table tr:last-child td { border-bottom: none; }
.movers-table .col-rank { color: var(--dim); width: 28px; text-align: center; }
.movers-table .col-name { color: var(--text); font-weight: 500; }
.movers-table .col-price { font-variant-numeric: tabular-nums; color: var(--muted); }
.movers-table .col-pct   { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }

/* ── Commodity detail modal ──────────────────────────────────── */
.modal-header { margin-bottom: 22px; padding-right: 80px; }
.modal-title-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.modal-badge { font-size: 0.75rem; font-weight: 700; color: var(--muted); background: var(--raised); border: 1px solid var(--border); padding: 3px 10px; border-radius: 6px; letter-spacing: 0.04em; }
.modal-name  { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; }
.modal-price-row { display: flex; align-items: baseline; gap: 14px; }
.modal-price { font-size: 2.15rem; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.03em; }
.modal-chg   { font-size: 1rem; font-weight: 600; }
.chart-section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.chart-section-label  { font-size: 0.62rem; font-weight: 600; letter-spacing: 0.15em; text-transform: uppercase; color: var(--dim); }
.range-tabs { display: flex; gap: 2px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 3px; }
.range-tab  { background: none; border: none; color: var(--muted); font-family: inherit; font-size: 0.7rem; font-weight: 600; padding: 4px 12px; border-radius: 5px; cursor: pointer; transition: background 0.15s, color 0.15s; letter-spacing: 0.05em; }
.range-tab:hover { color: var(--text); }
.range-tab.active { background: var(--raised); color: var(--text); border: 1px solid var(--border); }
.chart-wrap { position: relative; height: 230px; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; margin-bottom: 26px; }
#price-chart { display: none; }
.articles-section { margin-bottom: 26px; }
.articles-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (max-width: 640px) { .articles-grid { grid-template-columns: 1fr; } }
.article-card { display: flex; flex-direction: column; gap: 7px; padding: 14px 15px; background: var(--raised); border: 1px solid var(--border); border-radius: 10px; text-decoration: none; color: inherit; transition: border-color 0.15s, background 0.15s, transform 0.15s; }
.article-card:hover { border-color: var(--modal-accent, #3b82f6); background: var(--hover); transform: translateY(-2px); }
.article-publisher { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--modal-accent, #3b82f6); }
.article-title     { font-size: 0.82rem; font-weight: 600; color: var(--text); line-height: 1.45; }
.article-snippet   { font-size: 0.75rem; color: var(--muted); line-height: 1.6; flex: 1; }
.article-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 2px; }
.article-date { font-size: 0.65rem; color: var(--dim); }
.article-cta  { font-size: 0.68rem; font-weight: 600; color: var(--modal-accent, #3b82f6); }
.no-articles  { font-size: 0.78rem; color: var(--muted); padding: 12px 0; text-align: center; }
.summary-overview { font-size: 0.86rem; color: var(--text); line-height: 1.75; margin-bottom: 20px; }
.summary-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 20px; }
@media (max-width: 580px) { .summary-cols { grid-template-columns: 1fr; } }
.summary-col-heading { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--modal-accent, #3b82f6); margin-bottom: 10px; }
.summary-col ul { list-style: none; padding: 0; }
.summary-col ul li { font-size: 0.78rem; color: var(--muted); line-height: 1.65; padding: 4px 0 4px 16px; position: relative; border-bottom: 1px solid var(--border); }
.summary-col ul li:last-child { border-bottom: none; }
.summary-col ul li::before { content: '›'; position: absolute; left: 0; color: var(--modal-accent, #3b82f6); font-size: 1rem; }
.context-list { list-style: none; padding: 0; }
.context-list li { padding: 6px 0 6px 16px; position: relative; border-bottom: 1px solid var(--border); }
.context-list li:last-child { border-bottom: none; }
.context-list li::before { content: '›'; position: absolute; left: 0; color: var(--modal-accent, #3b82f6); font-size: 1rem; line-height: 1.5; }
.context-list a { font-size: 0.78rem; color: var(--text); text-decoration: none; line-height: 1.5; display: block; transition: color 0.12s; }
.context-list a:hover { color: var(--modal-accent, #3b82f6); }
.context-meta { font-size: 0.62rem; color: var(--dim); margin-top: 2px; }
.outlook-box { background: var(--bg); border-left: 3px solid var(--modal-accent, #3b82f6); border-radius: 0 8px 8px 0; padding: 14px 18px; font-size: 0.84rem; color: var(--text); line-height: 1.7; }
.outlook-label { font-size: 0.58rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--modal-accent, #3b82f6); margin-bottom: 7px; }

/* ── Footer ──────────────────────────────────────────────────── */
.footer {
  text-align: center; padding: 22px 28px 26px;
  color: var(--dim); font-size: 0.66rem;
  border-top: 1px solid var(--border);
  margin-top: 32px; line-height: 1.8;
}

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--raised); border-radius: 3px; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 640px) {
  .header { padding: 10px 14px; }
  .page   { padding: 20px 14px 40px; }
  .modal  { padding: 20px 16px 24px; }
  .briefing-grid { grid-template-columns: 1fr; }
  .modal-price { font-size: 1.65rem; }
  .modal-name  { font-size: 1.2rem; }
}
</style>
</head>
<body>

<!-- ── Side drawer backdrop ── -->
<div class="drawer-backdrop" id="drawer-backdrop"></div>

<!-- ── Side drawer ── -->
<nav class="side-drawer" id="side-drawer">
  <div class="drawer-header">
    <div class="drawer-brand">
      <div class="header-logo">M</div>
      <span>Market Snapshot</span>
    </div>
    <button class="drawer-close" onclick="closeDrawer()">&#x2715;</button>
  </div>
  <div class="drawer-section-label">Navigation</div>
  <div class="drawer-nav">
    <div class="drawer-link active" id="nav-home" onclick="showView('home')">
      <span class="drawer-link-icon">&#8962;</span> Home
    </div>
    <div class="drawer-link" id="nav-commodities" onclick="showView('commodities')">
      <span class="drawer-link-icon">&#9670;</span> Commodities
    </div>
  </div>
</nav>

<!-- ── Header ── -->
<header class="header">
  <div class="header-left">
    <button class="hamburger-btn" id="menu-btn" onclick="openDrawer()" title="Menu">
      <span></span><span></span><span></span>
    </button>
    <div class="header-logo">M</div>
    <span class="header-title">Market Snapshot</span>
  </div>
  <div class="header-right">
    <div class="clock" id="clock">--</div>
    <div class="refresh-row">
      <span class="live-dot"></span>
      <span class="refresh-label">Next update <b id="countdown">__REFRESH__</b>s</span>
      <div class="progress-track">
        <div class="progress-fill" id="progress-fill" style="width:100%"></div>
      </div>
    </div>
  </div>
</header>

<!-- ── Home View ── -->
<div class="view active" id="view-home">
  <main class="page">
    <h1 class="page-title">Market Briefing</h1>
    <p class="page-subtitle" id="date-line">Loading&hellip;</p>

    <div class="section-label">Today&rsquo;s Overview</div>
    <div class="briefing-grid" id="briefing-grid">

      <!-- Biggest Movers card -->
      <div class="bcard" id="card-movers" style="--accent:#f59e0b" onclick="openBriefingModal('movers')">
        <div class="bcard-accent"></div>
        <div class="bcard-tag">Live</div>
        <div class="bcard-title">Biggest Movers</div>
        <div class="bcard-body" id="preview-movers">
          <div style="color:#f59e0b;font-weight:600;font-size:0.95rem;margin-bottom:6px;">&#9650; Loading top movers&hellip;</div>
          <div style="color:var(--muted);font-size:0.82rem;">Live 24h changes loading. Click to see full rankings.</div>
        </div>
        <div class="bcard-footer">
          <span>24h daily change</span>
          <span class="bcard-cta">See all &rarr;</span>
        </div>
      </div>

      <!-- Key Market News card -->
      <div class="bcard" id="card-news" style="--accent:#10b981" onclick="openBriefingModal('news')">
        <div class="bcard-accent"></div>
        <div class="bcard-tag">News</div>
        <div class="bcard-title">Key Market News</div>
        <div class="bcard-body" id="preview-news">
          <div style="color:#10b981;font-weight:600;font-size:0.95rem;margin-bottom:6px;">&#9679; Headlines loading&hellip;</div>
          <div style="color:var(--muted);font-size:0.82rem;">Latest market headlines sourced from Yahoo Finance. Click to read.</div>
        </div>
        <div class="bcard-footer">
          <span>Yahoo Finance</span>
          <span class="bcard-cta">Read more &rarr;</span>
        </div>
      </div>

      <!-- Today's Market Drivers card -->
      <div class="bcard" id="card-drivers" style="--accent:#8b5cf6" onclick="openBriefingModal('drivers')">
        <div class="bcard-accent"></div>
        <div class="bcard-tag">Macro</div>
        <div class="bcard-title">Today&rsquo;s Market Drivers</div>
        <div class="bcard-body" id="preview-drivers">
          <div style="color:#8b5cf6;font-weight:600;font-size:0.95rem;margin-bottom:6px;">&#9670; Macro drivers loading&hellip;</div>
          <div style="color:var(--muted);font-size:0.82rem;">Fed policy, inflation data, geopolitical risk. Click for full briefing.</div>
        </div>
        <div class="bcard-footer">
          <span>Google News</span>
          <span class="bcard-cta">See all &rarr;</span>
        </div>
      </div>

    </div><!-- /briefing-grid -->
  </main>
</div><!-- /view-home -->

<!-- ── Commodities View ── -->
<div class="view" id="view-commodities">
  <main class="page">
    <h1 class="page-title">Live Markets</h1>
    <p class="page-subtitle">Real-time prices &mdash; click any instrument for chart, news &amp; analysis</p>
    <div class="section-label">Live Prices &mdash; vs prev. close</div>
    <div class="grid" id="grid"></div>
  </main>
</div><!-- /view-commodities -->

<!-- ── Footer ── -->
<footer class="footer">
  Data &mdash; CoinGecko &nbsp;&middot;&nbsp; Yahoo Finance &nbsp;&middot;&nbsp; Frankfurter.app &nbsp;&middot;&nbsp; Google News
  <br>Auto-refreshes every __REFRESH__ seconds &nbsp;&middot;&nbsp; All times UTC &nbsp;&middot;&nbsp; For informational purposes only
</footer>

<!-- ── Briefing Modal ── -->
<div class="overlay" id="briefing-overlay">
  <div class="modal" id="briefing-modal">
    <button class="modal-close" id="briefing-close-btn">&#x2715;&ensp;Close</button>
    <div class="modal-title"    id="bm-title"></div>
    <div class="modal-subtitle" id="bm-subtitle"></div>
    <div class="modal-divider"></div>
    <div id="briefing-modal-body"></div>
  </div>
</div>

<!-- ── Commodity Detail Modal ── -->
<div class="overlay" id="overlay">
  <div class="modal" id="modal">
    <button class="modal-close" id="close-btn">&#x2715;&ensp;Close</button>

    <div class="modal-header">
      <div class="modal-title-row">
        <span class="modal-badge" id="m-icon"></span>
        <span class="modal-name"  id="m-name"></span>
      </div>
      <div class="modal-price-row">
        <span class="modal-price" id="m-price">--</span>
        <span class="modal-chg"   id="m-chg"></span>
      </div>
    </div>

    <div class="chart-section-header">
      <span class="chart-section-label">Price History</span>
      <div class="range-tabs">
        <button class="range-tab" data-range="1d"  onclick="changeRange('1d')">24H</button>
        <button class="range-tab active" data-range="1mo" onclick="changeRange('1mo')">1M</button>
        <button class="range-tab" data-range="1y"  onclick="changeRange('1y')">1Y</button>
      </div>
    </div>
    <div class="chart-wrap">
      <div class="placeholder" id="chart-ph"><span class="spin"></span>Loading chart&hellip;</div>
      <canvas id="price-chart"></canvas>
    </div>

    <div class="articles-section">
      <div class="modal-divider"></div>
      <div class="section-label" style="margin-bottom:12px;">Latest Articles</div>
      <div id="articles-area">
        <div class="placeholder"><span class="spin"></span>Loading articles&hellip;</div>
      </div>
    </div>

    <div class="modal-divider"></div>
    <div class="section-label" style="margin-bottom:16px;">Macro &amp; Geopolitical Analysis</div>
    <div id="summary-area">
      <div class="placeholder"><span class="spin"></span>Loading analysis&hellip;</div>
    </div>
  </div>
</div>

<script>
/* ── Utilities ─────────────────────────────────────────────────────────────── */
function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function fmtPct(pct) {
  if (pct === null || pct === undefined) return { html: '<span class="neu">&mdash;</span>', cls: 'neu' };
  const cls   = pct > 0 ? 'up' : pct < 0 ? 'down' : 'neu';
  const arrow = pct > 0 ? '&#9650;' : pct < 0 ? '&#9660;' : '';
  const sign  = pct > 0 ? '+' : '';
  return { html: `<span class="${cls}">${arrow} ${sign}${pct.toFixed(2)}%</span>`, cls };
}

function fmtPrice(inst) {
  if (inst.price == null) return inst.error ? 'Error' : 'Loading\u2026';
  const s = inst.thousands
    ? inst.price.toLocaleString('en-US', { minimumFractionDigits: inst.decimals, maximumFractionDigits: inst.decimals })
    : inst.price.toFixed(inst.decimals);
  return inst.prefix + s + inst.suffix;
}

function calcChg(inst) {
  if (inst.price == null || inst.prev_price == null || inst.prev_price === 0) return null;
  return (inst.price - inst.prev_price) / inst.prev_price * 100;
}

/* ── Clock & date ──────────────────────────────────────────────────────────── */
function tickClock() {
  document.getElementById('clock').textContent =
    new Date().toUTCString().replace(' GMT', '') + ' UTC';
}
setInterval(tickClock, 1000); tickClock();

document.getElementById('date-line').textContent =
  new Date().toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' });

/* ── Refresh countdown ─────────────────────────────────────────────────────── */
const REFRESH = __REFRESH__;
let countdown = REFRESH;
setInterval(() => {
  countdown = Math.max(0, countdown - 1);
  document.getElementById('countdown').textContent = countdown;
  document.getElementById('progress-fill').style.width = (countdown / REFRESH * 100) + '%';
}, 1000);

/* ── Side drawer ───────────────────────────────────────────────────────────── */
function openDrawer() {
  document.getElementById('side-drawer').classList.add('open');
  document.getElementById('drawer-backdrop').classList.add('open');
}
function closeDrawer() {
  document.getElementById('side-drawer').classList.remove('open');
  document.getElementById('drawer-backdrop').classList.remove('open');
}
document.getElementById('drawer-backdrop').addEventListener('click', closeDrawer);

/* ── View switching ────────────────────────────────────────────────────────── */
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');
  document.querySelectorAll('.drawer-link').forEach(l => l.classList.remove('active'));
  document.getElementById('nav-' + name).classList.add('active');
  closeDrawer();
}

/* ── Price card state ──────────────────────────────────────────────────────── */
let instruments = [];

function renderCards(data) {
  instruments = data;
  const grid = document.getElementById('grid');

  if (grid.children.length === 0) {
    data.forEach(inst => {
      const card = document.createElement('div');
      card.className = 'card';
      card.id = 'card-' + inst.key;
      card.style.setProperty('--accent', inst.accent);
      card.addEventListener('click', () => openCommodityModal(inst.key));
      card.innerHTML =
        '<div class="card-accent"></div>' +
        '<div class="card-icon">'  + inst.icon  + '</div>' +
        '<div class="card-name">'  + inst.label + '</div>' +
        '<div class="card-price loading" id="p-' + inst.key + '">Loading\u2026</div>' +
        '<div class="card-change"  id="c-' + inst.key + '"></div>' +
        '<div class="card-hint">Click for details \u2192</div>';
      grid.appendChild(card);
    });
  }

  data.forEach(inst => {
    const pEl = document.getElementById('p-' + inst.key);
    const cEl = document.getElementById('c-' + inst.key);
    if (!pEl) return;

    if (!inst.price && inst.error) {
      pEl.className = 'card-price err';
      pEl.textContent = 'Unavailable';
      cEl.innerHTML = '<span class="neu" style="font-size:0.6rem">' + esc(inst.error.substring(0, 45)) + '</span>';
      return;
    }
    pEl.className = 'card-price';
    pEl.textContent = fmtPrice(inst);

    const chg = calcChg(inst);
    if (chg === null) {
      cEl.innerHTML = '<span class="neu">\u2014</span>';
    } else if (chg > 0) {
      cEl.innerHTML = '<span class="up">\u25b2</span><span class="up">+' + chg.toFixed(2) + '%</span>';
    } else {
      cEl.innerHTML = '<span class="down">\u25bc</span><span class="down">' + chg.toFixed(2) + '%</span>';
    }
  });

  if (_moversData) {
    _moversData = [...data].sort((a, b) => {
      const pa = a.price != null && a.prev_price ? Math.abs((a.price - a.prev_price) / a.prev_price) : -1;
      const pb = b.price != null && b.prev_price ? Math.abs((b.price - b.prev_price) / b.prev_price) : -1;
      return pb - pa;
    });
    renderMoversPreview();
  }
}

async function fetchPrices() {
  try {
    const res = await fetch('/api/prices');
    renderCards(await res.json());
    countdown = REFRESH;
  } catch(e) { console.error('Price fetch failed:', e); }
}
fetchPrices();
setInterval(fetchPrices, REFRESH * 1000);

/* ── Briefing card loaders ─────────────────────────────────────────────────── */
let _moversData  = null;
let _newsData    = null;
let _driversData = null;

async function loadBriefingData() {
  const priceRes = await fetch('/api/prices').then(r => r.json()).catch(() => []);
  _moversData = [...priceRes].sort((a, b) => {
    const pa = a.price != null && a.prev_price ? Math.abs((a.price - a.prev_price) / a.prev_price) : -1;
    const pb = b.price != null && b.prev_price ? Math.abs((b.price - b.prev_price) / b.prev_price) : -1;
    return pb - pa;
  });
  renderMoversPreview();

  const [news, drivers] = await Promise.all([
    fetch('/api/home/news').then(r => r.json()).catch(() => []),
    fetch('/api/home/drivers').then(r => r.json()).catch(() => []),
  ]);
  _newsData    = news;
  _driversData = drivers;
  renderNewsPreview();
  renderDriversPreview();
}
loadBriefingData();

/* ── Briefing card preview renderers ──────────────────────────────────────── */
function renderMoversPreview() {
  const el = document.getElementById('preview-movers');
  if (!el || !_moversData) return;
  const top = _moversData.filter(r => r.price != null).slice(0, 3);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No data yet</span>'; return; }
  el.innerHTML = '<div>' + top.map(r => {
    const pct = r.price != null && r.prev_price ? (r.price - r.prev_price) / r.prev_price * 100 : null;
    const { html } = fmtPct(pct);
    return `<div class="mover-row">
      <span class="mover-name">${esc(r.label)}</span>
      <span class="mover-pct">${html}</span>
    </div>`;
  }).join('') + '</div>';
}

function renderNewsPreview() {
  const el = document.getElementById('preview-news');
  const top = (_newsData || []).slice(0, 3);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No articles loaded</span>'; return; }
  el.innerHTML = '<ul class="bcard-preview-list">' +
    top.map(a => `<li title="${esc(a.title)}">${esc(a.title)}</li>`).join('') + '</ul>';
}

function renderDriversPreview() {
  const el = document.getElementById('preview-drivers');
  const top = (_driversData || []).slice(0, 3);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No headlines loaded</span>'; return; }
  el.innerHTML = '<ul class="bcard-preview-list">' +
    top.map(d => `<li title="${esc(d.title)}">${esc(d.title)}</li>`).join('') + '</ul>';
}

/* ── Briefing modal ────────────────────────────────────────────────────────── */
const BRIEFING_CONFIG = {
  movers:  { title: 'Biggest Movers',        subtitle: 'All instruments ranked by 24h % change', accent: '#f59e0b' },
  news:    { title: 'Key Market News',        subtitle: 'Latest articles aggregated across all instruments', accent: '#10b981' },
  drivers: { title: "Today\u2019s Market Drivers", subtitle: 'Top macro & market headlines from Google News', accent: '#8b5cf6' },
};

function openBriefingModal(key) {
  const cfg = BRIEFING_CONFIG[key];
  if (!cfg) return;
  const modal = document.getElementById('briefing-modal');
  modal.style.setProperty('--modal-accent', cfg.accent);
  modal.style.borderTopColor = cfg.accent;
  document.getElementById('bm-title').textContent    = cfg.title;
  document.getElementById('bm-subtitle').textContent = cfg.subtitle;
  const body = document.getElementById('briefing-modal-body');
  if      (key === 'movers')  body.innerHTML = buildMoversModal();
  else if (key === 'news')    body.innerHTML = buildNewsModal();
  else if (key === 'drivers') body.innerHTML = buildDriversModal();
  document.getElementById('briefing-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeBriefingModal() {
  document.getElementById('briefing-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
document.getElementById('briefing-close-btn').addEventListener('click', closeBriefingModal);
document.getElementById('briefing-overlay').addEventListener('click', e => {
  if (e.target.id === 'briefing-overlay') closeBriefingModal();
});

function buildMoversModal() {
  if (!_moversData || !_moversData.length) return '<p style="color:var(--muted)">No data available.</p>';
  const rows = _moversData.map((r, i) => {
    const pct = r.price != null && r.prev_price ? (r.price - r.prev_price) / r.prev_price * 100 : null;
    const { html, cls } = fmtPct(pct);
    return `<tr>
      <td class="col-rank">${i + 1}</td>
      <td class="col-name">${esc(r.label)}</td>
      <td class="col-price">${esc(fmtPrice(r))}</td>
      <td class="col-pct ${cls}">${html}</td>
    </tr>`;
  }).join('');
  return `<table class="movers-table"><tbody>${rows}</tbody></table>`;
}

function buildNewsModal() {
  if (!_newsData || !_newsData.length) return '<p style="color:var(--muted)">No articles available.</p>';
  return '<ul class="news-list">' + _newsData.map(a => `
    <li>
      <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>
      <div class="news-meta">
        ${esc(a.instrument || '')}
        ${a.publisher ? ' &middot; ' + esc(a.publisher) : ''}
        ${a.published ? ' &middot; ' + esc(a.published) : ''}
      </div>
    </li>`).join('') + '</ul>';
}

function buildDriversModal() {
  if (!_driversData || !_driversData.length) return '<p style="color:var(--muted)">No headlines available.</p>';
  return '<ul class="news-list">' + _driversData.map(d => `
    <li>
      <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
      <div class="news-meta">
        ${esc(d.source || '')}${d.published ? ' &middot; ' + esc(d.published) : ''}
      </div>
    </li>`).join('') + '</ul>';
}

/* ── Commodity detail modal ────────────────────────────────────────────────── */
let chart        = null;
let currentKey   = null;
let currentRange = '1mo';

async function openCommodityModal(key) {
  const inst = instruments.find(i => i.key === key);
  if (!inst) return;
  currentKey   = key;
  currentRange = '1mo';

  document.getElementById('modal').style.setProperty('--modal-accent', inst.accent);
  document.getElementById('modal').style.borderTopColor = inst.accent;
  document.getElementById('m-icon').innerHTML    = inst.icon;
  document.getElementById('m-name').textContent  = inst.label;
  document.getElementById('m-price').textContent = fmtPrice(inst);

  const chg = calcChg(inst);
  const chgEl = document.getElementById('m-chg');
  if (chg === null) {
    chgEl.textContent = ''; chgEl.className = 'modal-chg';
  } else if (chg > 0) {
    chgEl.textContent = '\u25b2 +' + chg.toFixed(2) + '%';
    chgEl.className = 'modal-chg up';
  } else {
    chgEl.textContent = '\u25bc ' + chg.toFixed(2) + '%';
    chgEl.className = 'modal-chg down';
  }

  document.querySelectorAll('.range-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === '1mo');
  });
  resetChart();
  document.getElementById('articles-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading articles\u2026</div>';
  document.getElementById('summary-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading analysis\u2026</div>';

  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  const [histRes, summRes] = await Promise.all([
    fetch('/api/history/' + key + '?range=1mo'),
    fetch('/api/summary/' + key),
  ]);
  if (histRes.ok) renderChart(await histRes.json());
  else showChartError();
  if (summRes.ok) {
    const data = await summRes.json();
    renderArticles(data.articles, inst.accent);
    renderSummary(data);
  } else {
    document.getElementById('articles-area').innerHTML = '<p class="no-articles">Could not load articles.</p>';
    document.getElementById('summary-area').innerHTML  = '<p class="no-articles">Could not load analysis.</p>';
  }
}

async function changeRange(range) {
  if (range === currentRange || !currentKey) return;
  currentRange = range;
  document.querySelectorAll('.range-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === range);
  });
  resetChart();
  try {
    const res = await fetch('/api/history/' + currentKey + '?range=' + range);
    if (res.ok) renderChart(await res.json());
    else showChartError();
  } catch(e) { showChartError(); }
}

function closeCommodityModal() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  if (chart) { chart.destroy(); chart = null; }
  currentKey = null;
}
document.getElementById('close-btn').addEventListener('click', closeCommodityModal);
document.getElementById('overlay').addEventListener('click', e => {
  if (e.target.id === 'overlay') closeCommodityModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeBriefingModal(); closeCommodityModal(); }
});

/* ── Chart ─────────────────────────────────────────────────────────────────── */
function resetChart() {
  const ph = document.getElementById('chart-ph');
  const cv = document.getElementById('price-chart');
  ph.style.display = 'flex';
  ph.innerHTML = '<span class="spin"></span>&nbsp;Loading chart\u2026';
  cv.style.display = 'none';
  if (chart) { chart.destroy(); chart = null; }
}

function showChartError() {
  const ph = document.getElementById('chart-ph');
  ph.style.display = 'flex';
  ph.innerHTML = '<span style="color:var(--red);font-size:0.8rem">Chart data unavailable</span>';
}

function renderChart(hist) {
  const ph = document.getElementById('chart-ph');
  const cv = document.getElementById('price-chart');
  ph.style.display = 'none';
  cv.style.display = 'block';

  const prices  = hist.prices;
  const isUp    = prices.length > 1 && prices[prices.length - 1] >= prices[0];
  const lineCol = isUp ? '#22c55e' : '#ef4444';

  const ctx  = cv.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 210);
  grad.addColorStop(0, isUp ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: hist.labels,
      datasets: [{
        data: prices, borderColor: lineCol, borderWidth: 1.8,
        backgroundColor: grad, fill: true, tension: 0.3,
        pointRadius: 0, pointHoverRadius: 5,
        pointHoverBackgroundColor: lineCol,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#131e30',
          borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
          titleColor: '#6b7f9e', titleFont: { size: 11 },
          bodyColor: '#dde8f8',  bodyFont: { size: 12, weight: '600' },
          padding: 10, displayColors: false,
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.y;
              if (hist.thousands) {
                return hist.prefix + v.toLocaleString('en-US', {
                  minimumFractionDigits: hist.decimals,
                  maximumFractionDigits: hist.decimals,
                }) + hist.suffix;
              }
              return hist.prefix + v.toFixed(hist.decimals) + hist.suffix;
            }
          }
        }
      },
      scales: {
        x: {
          grid:   { color: 'rgba(255,255,255,0.04)' },
          border: { color: 'rgba(255,255,255,0.06)' },
          ticks:  { color: '#374d68', font: { size: 10 }, maxTicksLimit: 8, maxRotation: 0 }
        },
        y: {
          position: 'right',
          grid:   { color: 'rgba(255,255,255,0.04)' },
          border: { color: 'rgba(255,255,255,0.06)' },
          ticks: {
            color: '#374d68', font: { size: 10 },
            callback: v => {
              if (hist.thousands)
                return hist.prefix + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
              return hist.prefix + v.toFixed(Math.min(hist.decimals, 3));
            }
          }
        }
      }
    }
  });
}

/* ── Articles ───────────────────────────────────────────────────────────────── */
function renderArticles(articles, accent) {
  const area = document.getElementById('articles-area');
  if (!articles || articles.length === 0) {
    area.innerHTML = '<p class="no-articles">No articles available at this time.</p>';
    return;
  }
  const cards = articles.map(a => `
    <a class="article-card" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
      <div class="article-publisher">${esc(a.publisher || 'News')}</div>
      <div class="article-title">${esc(a.title)}</div>
      ${a.summary ? `<div class="article-snippet">${esc(a.summary)}</div>` : ''}
      <div class="article-footer">
        <span class="article-date">${esc(a.published)}</span>
        <span class="article-cta">Read more &rarr;</span>
      </div>
    </a>
  `).join('');
  area.innerHTML = `<div class="articles-grid">${cards}</div>`;
}

/* ── Summary (macro / geopolitical / outlook) ──────────────────────────────── */
function renderSummary(data) {
  let html = '';
  html += `<p class="summary-overview">${esc(data.overview)}</p>`;

  const hasContext = data.context && data.context.length > 0;
  const half = hasContext ? Math.ceil(data.context.length / 2) : 0;
  const colA = hasContext ? data.context.slice(0, half) : null;
  const colB = hasContext ? data.context.slice(half)    : null;

  html += '<div class="summary-cols">';

  html += '<div class="summary-col">';
  html += '<div class="summary-col-heading">' + (hasContext ? 'Current Macro Context' : 'Macro Factors') + '</div>';
  if (hasContext && colA.length) {
    html += '<ul class="context-list">' + colA.map(item =>
      `<li>
        <a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
        <div class="context-meta">${esc(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
      </li>`
    ).join('') + '</ul>';
  } else {
    html += '<ul>' + data.macro.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>';
  }
  html += '</div>';

  html += '<div class="summary-col">';
  html += '<div class="summary-col-heading">' + (hasContext ? 'Market &amp; Geopolitical News' : 'Geopolitical Drivers') + '</div>';
  if (hasContext && colB.length) {
    html += '<ul class="context-list">' + colB.map(item =>
      `<li>
        <a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
        <div class="context-meta">${esc(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
      </li>`
    ).join('') + '</ul>';
  } else {
    html += '<ul>' + data.geopolitical.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>';
  }
  html += '</div>';

  html += '</div>';
  html += `
    <div class="outlook-box">
      <div class="outlook-label">Outlook</div>
      ${esc(data.outlook)}
    </div>`;

  document.getElementById('summary-area').innerHTML = html;
}
</script>
</body>
</html>
"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return COMBINED_HTML.replace("__REFRESH__", str(REFRESH_SECONDS))

@app.route("/dashboard")
def dashboard_redirect():
    from flask import redirect
    return redirect("/", code=301)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not YFINANCE_AVAILABLE:
        print("[WARN] yfinance not installed — commodity prices will fail.")
        print("       Run:  pip install yfinance")

    print(f"Fetching initial prices for {len(INSTRUMENTS)} instruments…")
    refresh_prices()
    print("Done. Starting background refresh thread.\n")

    bg = threading.Thread(target=_background_loop, daemon=True)
    bg.start()

    print("  Market Snapshot  ·  http://192.168.40.85:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)

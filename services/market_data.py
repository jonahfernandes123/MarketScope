from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False


# ── HTTP helper ─────────────────────────────────────────────────────────────────

def _get(url, params=None, timeout=12):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── Live price fetchers ──────────────────────────────────────────────────────────

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


# ── History fetchers (range-aware) ──────────────────────────────────────────────

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

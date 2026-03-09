from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

import requests


# ── Multi-period change calculation ─────────────────────────────────────────────

def _compute_changes(closes) -> dict:
    """Compute 1D / 1W / 1M / 1Y % changes from a sorted daily close pandas Series.

    For each lookback period, finds the last available close on or before
    (latest_date - N calendar days), satisfying the requirement that weekends /
    holidays use the nearest prior trading session.

    Returns change_1d, change_1w, change_1mo, change_1y as rounded floats or None.
    """
    empty = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    if len(closes) < 2:
        return empty

    current = float(closes.iloc[-1])

    # Normalise index to UTC-aware DatetimeIndex for calendar arithmetic
    idx = closes.index
    try:
        utc_idx = idx.tz_convert("UTC")
    except TypeError:
        utc_idx = idx.tz_localize("UTC")

    latest = utc_idx[-1]

    def _ref_close(days_back: int):
        target = latest - timedelta(days=days_back)
        positions = (utc_idx <= target).nonzero()[0]
        if not len(positions):
            return None
        return float(closes.iloc[positions[-1]])

    def _pct(ref):
        if ref is None or ref == 0:
            return None
        return round((current - ref) / ref * 100, 3)

    return {
        "change_1d":  _pct(float(closes.iloc[-2])),  # previous session close
        "change_1w":  _pct(_ref_close(7)),
        "change_1mo": _pct(_ref_close(30)),
        "change_1y":  _pct(_ref_close(365)),
    }

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
    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    if YFINANCE_AVAILABLE:
        try:
            hist = yf.Ticker("BTC-USD").history(period="1y", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                prev_price = float(closes.iloc[-2])
                changes = _compute_changes(closes)
        except Exception:
            pass
    return price, prev_price, changes


def fetch_ethereum():
    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": "ethereum", "vs_currencies": "usd"},
    )
    price = float(data["ethereum"]["usd"])
    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    if YFINANCE_AVAILABLE:
        try:
            hist = yf.Ticker("ETH-USD").history(period="1y", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                prev_price = float(closes.iloc[-2])
                changes = _compute_changes(closes)
        except Exception:
            pass
    return price, prev_price, changes


def fetch_eurusd():
    data = _get("https://api.frankfurter.app/latest", params={"from": "EUR", "to": "USD"})
    price = float(data["rates"]["USD"])
    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    if YFINANCE_AVAILABLE:
        try:
            hist = yf.Ticker("EURUSD=X").history(period="1y", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                prev_price = float(closes.iloc[-2])
                changes = _compute_changes(closes)
        except Exception:
            pass
    return price, prev_price, changes


def fetch_yf(ticker: str) -> tuple:
    if not YFINANCE_AVAILABLE:
        raise RuntimeError("yfinance not installed — run: pip install yfinance")
    hist = yf.Ticker(ticker).history(period="1y", interval="1d")
    if hist.empty:
        raise ValueError(f"No data returned for {ticker}")
    closes = hist["Close"].dropna()
    if len(closes) < 1:
        raise ValueError(f"No close prices for {ticker}")
    price = float(closes.iloc[-1])
    prev_price = float(closes.iloc[-2]) if len(closes) >= 2 else None
    changes = _compute_changes(closes)
    return price, prev_price, changes


# ── History fetchers (range-aware) ──────────────────────────────────────────────

# Date format applied to chart labels for each time range
_RANGE_LABEL_FMT = {"1d": "%H:%M", "1w": "%a %d", "1mo": "%b %d", "1y": "%b '%y"}

# yfinance period/interval config for each time range
_RANGE_YF_CFG = {
    "1d":  {"period": "1d",  "interval": "5m"},
    "1w":  {"period": "5d",  "interval": "1h"},
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
    days_map = {"1d": 1, "1w": 7, "1mo": 30, "1y": 365}
    days = days_map.get(range_param, 30)
    params: dict = {"vs_currency": "usd", "days": days}
    if days > 7:
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


def _history_ethereum(range_param: str) -> dict:
    days_map = {"1d": 1, "1w": 7, "1mo": 30, "1y": 365}
    days = days_map.get(range_param, 30)
    params: dict = {"vs_currency": "usd", "days": days}
    if days > 7:
        params["interval"] = "daily"
    data = _get(
        "https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
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
    if range_param in ("1d", "1w"):
        hist = yf.Ticker("EURUSD=X").history(**_RANGE_YF_CFG[range_param])
        if hist.empty:
            raise ValueError(f"No {range_param} EUR/USD data")
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
    """Generic yfinance price history for any ticker, with one retry on failure."""
    cfg  = _RANGE_YF_CFG.get(range_param, _RANGE_YF_CFG["1mo"])
    hist = None
    for attempt in range(2):
        try:
            hist = yf.Ticker(ticker).history(**cfg)
            if not hist.empty:
                break
            if attempt == 0:
                print(f"[WARN] Empty history for {ticker} ({range_param}), retrying…")
                time.sleep(0.8)
        except Exception as exc:
            if attempt == 1:
                raise
            print(f"[WARN] History fetch error for {ticker} ({range_param}): {exc}, retrying…")
            time.sleep(0.8)

    # 1W fallback: try 2h interval if 1h returned empty
    if (hist is None or hist.empty) and range_param == "1w":
        print(f"[WARN] Falling back to 2h interval for {ticker} 1W chart")
        hist = yf.Ticker(ticker).history(period="5d", interval="2h")

    if hist is None or hist.empty:
        raise ValueError(f"No history for {ticker} ({range_param})")
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")
    return {
        "labels": _fmt_index_labels(hist.index, fmt),
        "prices": [round(float(v), 6) for v in hist["Close"]],
    }

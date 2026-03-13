from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
import time

import requests


# ── CoinGecko shared cache ───────────────────────────────────────────────────────
# A single shared cache for all CoinGecko simple/price calls so that concurrent
# threads (BTC + ETH fetching simultaneously) never fire more than one upstream
# request per TTL window.

_CG_CACHE_TTL   = 28          # seconds — slightly shorter than the 30 s refresh cycle
_cg_lock        = threading.Lock()
_cg_cache: dict = {}          # key → {"data": ..., "ts": float}


# ── Binance real-time crypto cache ───────────────────────────────────────────────
# Binance public REST API (no key required) returns real-time spot prices.
# Used as the primary source for BTC and ETH spot prices.

_BINANCE_TTL    = 12          # seconds — near-real-time, well below the 30 s refresh
_binance_lock   = threading.Lock()
_binance_cache: dict = {}     # symbol → {"price": float, "ts": float}


def _binance_get(symbols: list) -> dict:
    """Fetch real-time spot prices from Binance for a list of USDT symbols.

    Single combined request, TTL-cached.  Returns {symbol: price_float}.
    On error: serves stale cached prices where available; raises only on cold failure.
    """
    import json as _json
    now = time.monotonic()
    with _binance_lock:
        if all(
            sym in _binance_cache and (now - _binance_cache[sym]["ts"]) < _BINANCE_TTL
            for sym in symbols
        ):
            return {sym: _binance_cache[sym]["price"] for sym in symbols}

    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbols": _json.dumps(symbols)},
            timeout=8,
        )
        r.raise_for_status()
        now2 = time.monotonic()
        result: dict = {}
        with _binance_lock:
            for item in r.json():
                sym   = item["symbol"]
                price = float(item["price"])
                _binance_cache[sym] = {"price": price, "ts": now2}
                if sym in symbols:
                    result[sym] = price
        return result
    except Exception:
        with _binance_lock:
            stale = {sym: _binance_cache[sym]["price"] for sym in symbols if sym in _binance_cache}
        if stale:
            return stale
        raise


def _cg_get(url: str, params: dict | None = None, timeout: int = 12):
    """GET a CoinGecko endpoint with an in-process TTL cache.

    On 429 / any temporary error: returns the last cached response if available,
    otherwise re-raises so the caller can fall back to stale price_cache values.
    """
    cache_key = url + str(sorted((params or {}).items()))
    with _cg_lock:
        entry = _cg_cache.get(cache_key)
        if entry and (time.monotonic() - entry["ts"]) < _CG_CACHE_TTL:
            return entry["data"]

    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        # On any failure, serve stale cache if available; otherwise propagate.
        with _cg_lock:
            entry = _cg_cache.get(cache_key)
        if entry:
            return entry["data"]
        raise

    with _cg_lock:
        _cg_cache[cache_key] = {"data": data, "ts": time.monotonic()}
    return data


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
        "change_1d":  _pct(float(closes.iloc[-2])),  # previous session close (overridden in callers when live price available)
        "change_1w":  _pct(_ref_close(7)),
        "change_1mo": _pct(_ref_close(30)),
        "change_1y":  _pct(_ref_close(365)),
    }


def _daily_prev_close(cd) -> float | None:
    """Return the daily close that serves as the reference for today's 1d change.

    When markets are open:
      - The daily series ends at yesterday's close (cd[-1] = yesterday).
      - We return cd[-1] so the 1d change reads: (live_price - yesterday) / yesterday.

    When markets are closed / session already settled:
      - Today's close is at cd[-1]; yesterday is at cd[-2].
      - We return cd[-2].

    This ensures the displayed 1d change always compares the current price
    against the most recent completed prior-session close.
    """
    if len(cd) < 1:
        return None
    last_idx = cd.index[-1]
    today = datetime.now(timezone.utc).date()
    try:
        if hasattr(last_idx, "tz_convert"):
            last_date = last_idx.tz_convert(timezone.utc).date()
        elif hasattr(last_idx, "tz_localize"):
            last_date = last_idx.tz_localize(timezone.utc).date()
        else:
            last_date = last_idx.date()
    except Exception:
        last_date = today  # conservative: assume today's bar is present
    if last_date >= today:
        # Today's session already in the daily data → prev close is cd[-2]
        return float(cd.iloc[-2]) if len(cd) >= 2 else None
    # Daily series ends before today → cd[-1] IS yesterday's (prev-session) close
    return float(cd.iloc[-1])

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


# ── yfinance TTL cache ───────────────────────────────────────────────────────────
# Caches per (ticker, period, interval) for _YF_TTL seconds.
# - Prevents concurrent refresh threads from all hitting Yahoo simultaneously.
# - On upstream failure, returns the last successful DataFrame (stale fallback).

_YF_TTL       = 55                # seconds — survive two 30 s refresh cycles
_yf_cache_lock = threading.Lock()
_yf_cache_data: dict = {}         # (ticker, period, interval) → {"hist": df, "ts": float}


def _yf_fetch(ticker: str, period: str, interval: str):
    """Fetch yfinance history with in-process TTL cache.

    Returns a DataFrame (possibly stale on error) or None on total cold failure.
    Never raises — callers should check `hist is None or hist.empty`.
    """
    if not YFINANCE_AVAILABLE:
        return None

    key = (ticker, period, interval)

    with _yf_cache_lock:
        entry = _yf_cache_data.get(key)
        if entry and (time.monotonic() - entry["ts"]) < _YF_TTL:
            return entry["hist"]

    hist = None
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception:
        pass

    if hist is not None and not hist.empty:
        with _yf_cache_lock:
            _yf_cache_data[key] = {"hist": hist, "ts": time.monotonic()}
        return hist

    # Upstream empty/failed — return stale cache if available, otherwise hist (may be empty)
    with _yf_cache_lock:
        entry = _yf_cache_data.get(key)
    return entry["hist"] if entry else hist


# ── Live price fetchers ──────────────────────────────────────────────────────────

def _fetch_crypto_prices() -> dict:
    """Fetch BTC + ETH spot prices in a single CoinGecko request (cached)."""
    return _cg_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": "bitcoin,ethereum", "vs_currencies": "usd"},
    )


def _fetch_crypto_spot(binance_sym: str, cg_key: str) -> float | None:
    """Fetch a real-time crypto spot price using: Binance → CoinGecko → None.

    Never raises — returns None when all sources fail.
    """
    # 1. Binance (real-time, no key)
    try:
        prices = _binance_get([binance_sym])
        if binance_sym in prices:
            return prices[binance_sym]
    except Exception:
        pass

    # 2. CoinGecko (TTL-cached, rate-limited fallback)
    try:
        data = _fetch_crypto_prices()
        return float(data[cg_key]["usd"])
    except Exception:
        pass

    return None


def fetch_bitcoin():
    price = _fetch_crypto_spot("BTCUSDT", "bitcoin")

    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    hist = _yf_fetch("BTC-USD", "1y", "1d")
    if hist is not None and not hist.empty:
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            changes = _compute_changes(closes)
            # Anchor change_1d to live Binance price vs prev-session daily close.
            # _compute_changes uses cd[-1] as "current" which is yesterday's close
            # when markets are open — this fixes the inconsistency.
            ref = _daily_prev_close(closes)
            if ref is not None and ref != 0:
                prev_price = ref
                if price is not None:
                    changes["change_1d"] = round((price - ref) / ref * 100, 3)
        if price is None and len(closes) >= 1:
            price = float(closes.iloc[-1])   # yfinance as last-resort price source

    if price is None:
        raise ValueError("No BTC price from Binance, CoinGecko, or yfinance")
    return price, prev_price, changes


def fetch_ethereum():
    price = _fetch_crypto_spot("ETHUSDT", "ethereum")

    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    hist = _yf_fetch("ETH-USD", "1y", "1d")
    if hist is not None and not hist.empty:
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            changes = _compute_changes(closes)
            ref = _daily_prev_close(closes)
            if ref is not None and ref != 0:
                prev_price = ref
                if price is not None:
                    changes["change_1d"] = round((price - ref) / ref * 100, 3)
        if price is None and len(closes) >= 1:
            price = float(closes.iloc[-1])   # yfinance as last-resort price source

    if price is None:
        raise ValueError("No ETH price from Binance, CoinGecko, or yfinance")
    return price, prev_price, changes


def fetch_eurusd():
    # ── Intraday price from yfinance (~15-min delayed, more current than daily ECB rate) ──
    price = None
    hist_intra = _yf_fetch("EURUSD=X", "1d", "5m")
    if hist_intra is None or hist_intra.empty:
        hist_intra = _yf_fetch("EURUSD=X", "5d", "5m")
    if hist_intra is not None and not hist_intra.empty:
        ci = hist_intra["Close"].dropna()
        if len(ci) >= 1:
            price = float(ci.iloc[-1])

    # Fallback: Frankfurter.app official ECB daily rate
    if price is None:
        try:
            data = _get("https://api.frankfurter.app/latest", params={"from": "EUR", "to": "USD"})
            price = float(data["rates"]["USD"])
        except Exception:
            pass

    # ── Change calculations from daily history ──
    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}
    hist_daily = _yf_fetch("EURUSD=X", "1y", "1d")
    if hist_daily is not None and not hist_daily.empty:
        closes = hist_daily["Close"].dropna()
        if len(closes) >= 2:
            changes = _compute_changes(closes)
            ref = _daily_prev_close(closes)
            if ref is not None and ref != 0:
                prev_price = ref
                if price is not None:
                    changes["change_1d"] = round((price - ref) / ref * 100, 3)

    if price is None:
        raise ValueError("No EUR/USD price from yfinance or Frankfurter")
    return price, prev_price, changes


def fetch_yf(ticker: str) -> tuple:
    if not YFINANCE_AVAILABLE:
        raise RuntimeError("yfinance not installed — run: pip install yfinance")

    # ── Intraday price: most current bar available (~15-min delayed) ──
    hist_intra = _yf_fetch(ticker, "1d", "5m")
    if hist_intra is None or hist_intra.empty:
        hist_intra = _yf_fetch(ticker, "5d", "5m")  # handles rollover / weekends

    # ── Daily history: reference close and multi-period changes ──
    hist_daily = _yf_fetch(ticker, "1y", "1d")
    if hist_daily is None or hist_daily.empty:
        hist_daily = _yf_fetch(ticker, "5d", "1d")  # futures rollover fallback

    if (hist_intra is None or hist_intra.empty) and (hist_daily is None or hist_daily.empty):
        raise ValueError(f"No data returned for {ticker}")

    # Current price from intraday
    intra_price = None
    if hist_intra is not None and not hist_intra.empty:
        ci = hist_intra["Close"].dropna()
        if len(ci) >= 1:
            intra_price = float(ci.iloc[-1])

    # Daily close series
    cd = None
    if hist_daily is not None and not hist_daily.empty:
        cd = hist_daily["Close"].dropna()
        if cd.empty:
            cd = None

    # Sanity-check intraday vs daily: if they diverge by >20% the intraday
    # data is likely stale, wrong contract, or a rollover artifact — discard it.
    # This catches known data-quality issues with futures tickers (e.g. BZ=F).
    if intra_price is not None and cd is not None and len(cd) >= 1:
        daily_last = float(cd.iloc[-1])
        if daily_last > 0 and abs(intra_price - daily_last) / daily_last > 0.20:
            intra_price = None  # fall back to daily close

    price = intra_price
    if price is None and cd is not None and len(cd) >= 1:
        price = float(cd.iloc[-1])   # last resort: most recent daily close

    if price is None:
        raise ValueError(f"No close prices for {ticker}")

    prev_price = None
    changes = {"change_1d": None, "change_1w": None, "change_1mo": None, "change_1y": None}

    if cd is not None and len(cd) >= 2:
        # Multi-period changes (1w / 1mo / 1y) from the daily series
        changes = _compute_changes(cd)

        # Recompute change_1d anchored to the live intraday price vs prev-session close.
        # _compute_changes uses cd[-1] as "current" which equals yesterday's close when
        # markets are open, producing yesterday's change instead of today's.
        ref = _daily_prev_close(cd)
        if ref is not None and ref != 0:
            prev_price = ref
            if intra_price is not None:
                # Live price available: today's change = (live - prev_close) / prev_close
                changes["change_1d"] = round((intra_price - ref) / ref * 100, 3)
            # else: no valid intraday — keep daily-to-daily change_1d from _compute_changes

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
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")

    # Primary: CoinGecko market_chart endpoint
    try:
        params: dict = {"vs_currency": "usd", "days": days}
        if days > 7:
            params["interval"] = "daily"
        data = _cg_get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params=params, timeout=15,
        )
        pts = data["prices"]
        if not pts:
            raise ValueError("Empty prices list from CoinGecko")
        labels = [datetime.utcfromtimestamp(p[0] / 1000).strftime(fmt) for p in pts]
        prices = [round(p[1], 2) for p in pts]
        return {"labels": labels, "prices": prices}
    except Exception:
        pass

    # Fallback: yfinance BTC-USD
    return _history_yf("BTC-USD", range_param)


def _history_ethereum(range_param: str) -> dict:
    days_map = {"1d": 1, "1w": 7, "1mo": 30, "1y": 365}
    days = days_map.get(range_param, 30)
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")

    # Primary: CoinGecko market_chart endpoint
    try:
        params: dict = {"vs_currency": "usd", "days": days}
        if days > 7:
            params["interval"] = "daily"
        data = _cg_get(
            "https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
            params=params, timeout=15,
        )
        pts = data["prices"]
        if not pts:
            raise ValueError("Empty prices list from CoinGecko")
        labels = [datetime.utcfromtimestamp(p[0] / 1000).strftime(fmt) for p in pts]
        prices = [round(p[1], 2) for p in pts]
        return {"labels": labels, "prices": prices}
    except Exception:
        pass

    # Fallback: yfinance ETH-USD
    return _history_yf("ETH-USD", range_param)


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
    """Generic yfinance price history for any ticker, using TTL cache."""
    cfg  = _RANGE_YF_CFG.get(range_param, _RANGE_YF_CFG["1mo"])
    hist = _yf_fetch(ticker, cfg["period"], cfg["interval"])

    # 1W fallback: try 2h interval if 1h returned empty
    if (hist is None or hist.empty) and range_param == "1w":
        hist = _yf_fetch(ticker, "5d", "2h")

    if hist is None or hist.empty:
        raise ValueError(f"No history for {ticker} ({range_param})")
    fmt = _RANGE_LABEL_FMT.get(range_param, "%b %d")
    return {
        "labels": _fmt_index_labels(hist.index, fmt),
        "prices": [round(float(v), 6) for v in hist["Close"]],
    }

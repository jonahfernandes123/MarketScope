"""Futures term structure / forward curve data fetcher.

For instruments with curve_enabled=True, this module generates upcoming
contract symbols and fetches their last-traded prices via yfinance.

Contract symbol format (yfinance):  {ROOT}{MONTH_CODE}{YY}=F
  e.g.  CLJ26=F  =  WTI April 2026
        GCM26=F  =  Gold June 2026

Data source limitation:
  All curve data comes from Yahoo Finance via yfinance (~15-min delayed).
  Individual contract month coverage is best for COMEX/NYMEX front months;
  back-month and ICE contracts (e.g. TTF) are unreliable or unlisted in
  Yahoo Finance and are excluded from curve_enabled instruments.
  To swap the chain-price source, replace _fetch_chain_prices() only.

Data quality note:
  The curve reflects last-traded prices, not official settlements.
  Thin/expired contracts may return no data; those are excluded from
  the curve chart but listed as "unavailable" in the contracts array.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from datetime import datetime, timezone

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

log = logging.getLogger(__name__)

# Month code → calendar month number
_MONTH_CODES: dict[str, int] = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5,  "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Curve results are cached per instrument key for CURVE_TTL seconds.
# The forward curve changes slowly; 5-minute caching is appropriate.
_CURVE_TTL = 300
_curve_lock = threading.Lock()
_curve_cache: dict[str, dict] = {}


def _upcoming_contracts(
    root: str, active_months: list[str], n: int = 8
) -> list[tuple[str, str]]:
    """Generate the next N upcoming contract (symbol, label) pairs.

    Skips the current calendar month and earlier — most COMEX/NYMEX contracts
    expire in the third week of the prior month, so the current-month contract
    is near-expiry or already expired by the time it would be listed here.

    yfinance symbol format: {ROOT}{MONTH_CODE}{YY}=F
    """
    now = datetime.now(timezone.utc)
    cur_year, cur_month = now.year, now.month

    results: list[tuple[str, str]] = []
    check_year = cur_year

    while len(results) < n:
        for code in active_months:
            m = _MONTH_CODES[code]
            # Skip current month and earlier — current-month contracts are
            # near-expiry (COMEX/NYMEX expire mid-prior-month) and often
            # return stale or empty data from yfinance.
            if check_year == cur_year and m <= cur_month:
                continue
            symbol = f"{root}{code}{str(check_year)[-2:]}=F"
            label = f"{_MONTH_NAMES[m - 1]} {check_year}"
            results.append((symbol, label))
            if len(results) >= n:
                return results
        check_year += 1

    return results[:n]


def _fetch_yf_price(symbol: str) -> float | None:
    """Return the latest price for a specific futures contract symbol.

    Three-tier fetch strategy (fastest → most reliable):
      1. fast_info.last_price  — Yahoo quote API; works for active contracts
         without downloading OHLCV history. Fastest, but returns NaN for
         very thinly traded or delisted contracts.
      2. history(period="5d") — daily OHLCV; uses shared TTL cache in
         market_data. Covers most active front/second months.
      3. history(period="1mo") — broader window; catches contracts that
         had no trades in the last 5 calendar days (e.g. long weekends,
         thin back months).

    Returns None if all three tiers fail. Never raises.
    """
    if not _YF_AVAILABLE:
        return None

    # Tier 1: quote API (fast_info)
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.last_price
        if price is not None and price == price and price > 0:  # NaN check
            return round(float(price), 6)
    except Exception:
        pass

    # Tier 2: OHLCV 5-day (shared cache)
    try:
        from services.market_data import _yf_fetch  # avoid circular import
        hist = _yf_fetch(symbol, "5d", "1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            if len(closes) >= 1:
                return round(float(closes.iloc[-1]), 6)
    except Exception:
        pass

    # Tier 3: OHLCV 1-month (direct, no cache)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo", interval="1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            if len(closes) >= 1:
                return round(float(closes.iloc[-1]), 6)
    except Exception:
        pass

    return None


def _fetch_chain_prices(
    symbols: list[tuple[str, str]]
) -> dict[str, float | None]:
    """Fetch prices for a list of (symbol, label) contract pairs.

    This is the single swappable source function for the curve chain.
    To replace the data source (e.g. switch to a paid API), replace
    this function's body only — the rest of get_curve() is unchanged.

    Returns a dict mapping symbol → price (or None if unavailable).
    Uses a bounded thread pool to parallelise yfinance calls without
    triggering rate-limit bans.
    """
    prices: dict[str, float | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fut_map = {pool.submit(_fetch_yf_price, sym): sym for sym, _ in symbols}
        for fut in concurrent.futures.as_completed(fut_map):
            sym = fut_map[fut]
            try:
                prices[sym] = fut.result()
            except Exception as exc:
                log.warning("curve fetch error for %s: %s", sym, exc)
                prices[sym] = None
    return prices


def get_curve(inst: dict) -> dict:
    """Fetch and return the forward curve for one instrument.

    Args:
        inst: an entry from models.instruments.INSTRUMENTS
              (must include curve_root, curve_months, and optionally curve_n)

    Returns:
        {
          "contracts":       [{"symbol", "label", "price", "status"}, ...],
          "curve_state":     "contango" | "backwardation" | "flat" | "insufficient",
          "front_to_second": {"spread": float, "pct": float} | None,
          "front_to_sixth":  {"spread": float, "pct": float} | None,
          "source":          "yfinance",
          "ts":              ISO-8601 UTC string,
          "error":           str | None,
        }
    """
    key = inst.get("key", "__unknown__")

    # Return cached result if still fresh
    with _curve_lock:
        entry = _curve_cache.get(key)
        if entry and (time.monotonic() - entry["ts"]) < _CURVE_TTL:
            return entry["data"]

    ts = datetime.now(timezone.utc).isoformat()
    root = inst.get("curve_root")
    months = inst.get("curve_months", [])
    n = inst.get("curve_n", 8)

    if not root or not months:
        result = {
            "contracts": [], "curve_state": "insufficient",
            "front_to_second": None, "front_to_sixth": None,
            "source": "N/A", "ts": ts,
            "error": "No curve configuration for this instrument",
        }
        return result

    if not _YF_AVAILABLE:
        result = {
            "contracts": [], "curve_state": "insufficient",
            "front_to_second": None, "front_to_sixth": None,
            "source": "N/A", "ts": ts,
            "error": "yfinance not installed — cannot fetch contract chain",
        }
        return result

    symbols = _upcoming_contracts(root, months, n=n)
    prices = _fetch_chain_prices(symbols)

    contracts = [
        {
            "symbol": sym,
            "label":  label,
            "price":  prices.get(sym),
            "status": "delayed" if prices.get(sym) is not None else "unavailable",
        }
        for sym, label in symbols
    ]

    # Analytics on the valid sub-set
    valid = [c for c in contracts if c["price"] is not None]

    curve_state     = "insufficient"
    front_to_second = None
    front_to_sixth  = None

    if len(valid) >= 2:
        f1 = valid[0]["price"]
        f2 = valid[1]["price"]
        spread12 = f2 - f1
        pct12    = (spread12 / f1 * 100) if f1 != 0 else 0.0
        front_to_second = {"spread": round(spread12, 6), "pct": round(pct12, 4)}

        if abs(pct12) < 0.05:
            curve_state = "flat"
        elif spread12 > 0:
            curve_state = "contango"
        else:
            curve_state = "backwardation"

        if len(valid) >= 6:
            f6 = valid[5]["price"]
            spread16 = f6 - f1
            pct16    = (spread16 / f1 * 100) if f1 != 0 else 0.0
            front_to_sixth = {"spread": round(spread16, 6), "pct": round(pct16, 4)}

    result = {
        "contracts":        contracts,
        "curve_state":      curve_state,
        "front_to_second":  front_to_second,
        "front_to_sixth":   front_to_sixth,
        "source":           "yfinance",
        "ts":               ts,
        "error":            None if valid else "No contract prices available from yfinance",
    }

    with _curve_lock:
        _curve_cache[key] = {"data": result, "ts": time.monotonic()}

    return result

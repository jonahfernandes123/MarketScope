"""Futures term structure / forward curve data fetcher.

For instruments with curve_enabled=True, this module generates upcoming
contract symbols and fetches their last-traded prices via yfinance.

Contract symbol format (yfinance):  {ROOT}{MONTH_CODE}{YY}=F
  e.g.  CLJ26=F  =  WTI April 2026
        GCM26=F  =  Gold June 2026

Data quality note:
  All prices come from yfinance and carry a ~15-minute delay.
  The curve reflects last-traded prices, not official settlements.
  Thin/expired contracts may return no data; those are excluded from
  the curve but listed as "unavailable".
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from datetime import datetime, timezone

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

    Skips months that have already expired in the current calendar year.
    yfinance symbol format: {ROOT}{MONTH_CODE}{YY}=F
    """
    now = datetime.now(timezone.utc)
    cur_year, cur_month = now.year, now.month

    results: list[tuple[str, str]] = []
    check_year = cur_year

    while len(results) < n:
        for code in active_months:
            m = _MONTH_CODES[code]
            # Skip months that have already expired this year
            if check_year == cur_year and m < cur_month:
                continue
            symbol = f"{root}{code}{str(check_year)[-2:]}=F"
            label = f"{_MONTH_NAMES[m - 1]} {check_year}"
            results.append((symbol, label))
            if len(results) >= n:
                return results
        check_year += 1

    return results[:n]


def _fetch_one_contract(symbol: str) -> float | None:
    """Return the latest daily close for a specific futures contract.

    Uses the shared yfinance TTL cache so repeated calls are cheap.
    Returns None if the contract has no data (expired, too far forward, etc.).
    Never raises.
    """
    try:
        from services.market_data import _yf_fetch  # local import avoids circularity
        hist = _yf_fetch(symbol, "5d", "1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            if len(closes) >= 1:
                return round(float(closes.iloc[-1]), 6)
    except Exception:
        pass
    return None


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

    symbols = _upcoming_contracts(root, months, n=n)

    # Fetch all contracts concurrently (bounded, avoids rate-limit storms)
    prices: dict[str, float | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(_fetch_one_contract, sym): sym for sym, _ in symbols}
        for fut in concurrent.futures.as_completed(futs):
            prices[futs[fut]] = fut.result()

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

    curve_state    = "insufficient"
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
        "error":            None if valid else "No contract prices available",
    }

    with _curve_lock:
        _curve_cache[key] = {"data": result, "ts": time.monotonic()}

    return result

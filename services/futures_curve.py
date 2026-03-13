"""Futures term structure / forward curve data fetcher.

For instruments with curve_enabled=True, this module generates upcoming
contract symbols and fetches their last-traded prices via yfinance.

Contract symbol format (yfinance):  {ROOT}{MONTH_CODE}{YY}=F
  e.g.  CLJ26=F  =  WTI April 2026
        GCM26=F  =  Gold June 2026

Data source label: DELAYED
  All curve data comes from Yahoo Finance via yfinance (~15-min delayed).
  Individual contract month coverage is best for COMEX/NYMEX front months;
  back-month and ICE contracts (e.g. TTF, Brent BZ) are unreliable or
  unlisted in Yahoo Finance and are excluded from curve_enabled instruments.
  To swap the chain-price source, replace _fetch_chain_prices() only.

Data quality note:
  The curve reflects last-traded prices (~15-min delayed), not official
  settlements.  Thin/expired contracts may return no data; those are
  excluded from the curve chart but listed as "unavailable" in the
  contracts array.

Fetch strategy for back-month futures (why period= fails):
  Yahoo Finance's /v8/finance/chart endpoint does NOT return OHLCV rows
  for specific-expiry back-month futures (e.g. CLJ26=F) when called with
  the period= shorthand ("5d", "1mo", etc.).  The endpoint requires explicit
  start=/end= date parameters to return historical bars for these symbols.
  This is the root cause of the "No contract prices available" error with
  the previous history(period="5d") approach.

  The fix is:
    Tier 1 — history(start=..., end=...) with an explicit 30-day window.
              Reliably returns the last traded bar for COMEX/NYMEX back months.
    Tier 2 — info["regularMarketPrice"].
              Yahoo /v10/finance/quoteSummary populates regularMarketPrice
              for actively-traded back-month futures even when the chart
              endpoint fails.
    Tier 3 — fast_info.last_price.
              Yahoo /v7/finance/quote; frequently NaN for back-month futures.
              Kept as last resort.
"""

from __future__ import annotations

import concurrent.futures
import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider constant — swap this label (and _fetch_chain_prices body) to
# switch the entire curve chain to a different data source.
# ---------------------------------------------------------------------------
CURVE_PROVIDER = "yfinance"  # Replace with "refinitiv", "bloomberg", etc. when upgrading

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

# Honest source label for every price returned by this module.
# Yahoo Finance serves ~15-min delayed data; it is not live and not a
# settlement price.  "delayed" is the correct label per exchange rules.
_CURVE_SOURCE = "delayed"


def _upcoming_contracts(
    root: str, active_months: list[str], n: int = 8
) -> list[tuple[str, str]]:
    """Generate the next N upcoming contract (symbol, label) pairs.

    Skips the current calendar month and earlier — most COMEX/NYMEX contracts
    expire in the third week of the prior month, so the current-month contract
    is near-expiry or already expired by the time it would be listed here.

    Example for today 2026-03-13:
      WTI (CL, all 12 months): CLJ26=F (Apr), CLK26=F (May), CLM26=F (Jun),
        CLN26=F (Jul), CLQ26=F (Aug), CLU26=F (Sep), CLV26=F (Oct),
        CLX26=F (Nov) → 8 contracts
      Gold (GC, G/J/M/Q/V/Z): GCJ26=F (Apr), GCM26=F (Jun), GCQ26=F (Aug),
        GCV26=F (Oct), GCZ26=F (Dec), GCG27=F (Feb), GCJ27=F (Apr),
        GCM27=F (Jun) → 8 contracts

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
            # Example: on 2026-03-13, cur_month=3, so months 1,2,3 are skipped.
            # April (m=4) is the first contract listed.
            if check_year == cur_year and m <= cur_month:
                continue
            symbol = f"{root}{code}{str(check_year)[-2:]}=F"
            label = f"{_MONTH_NAMES[m - 1]} {check_year}"
            results.append((symbol, label))
            if len(results) >= n:
                return results
        check_year += 1

    return results[:n]


def _safe_positive_float(val) -> float | None:
    """Return val as float if it is a finite positive number, else None."""
    try:
        f = float(val)
        if math.isfinite(f) and f > 0:
            return f
    except Exception:
        pass
    return None


def _fetch_yf_price(symbol: str) -> float | None:
    """Return the latest price for a specific futures contract symbol.

    Three-tier fetch strategy (most reliable first for back-month contracts):

      Tier 1: history(start=..., end=...) with explicit date range.
        Yahoo Finance's chart endpoint requires explicit start/end dates to
        return OHLCV rows for specific-expiry back-month futures (e.g.
        CLJ26=F, GCM26=F).  The period= shorthand ("5d", "1mo") does NOT
        work for these symbols and returns empty DataFrames — this was the
        root cause of "No contract prices available".  An explicit 30-day
        window anchored to today's date reliably retrieves the last traded
        bar for COMEX/NYMEX back months.

      Tier 2: info["regularMarketPrice"].
        Yahoo /v10/finance/quoteSummary populates regularMarketPrice for
        actively-traded back-month futures even when the chart endpoint
        returns empty.  Slightly slower due to the extra round-trip.

      Tier 3: fast_info.last_price — Yahoo /v7/finance/quote.
        Frequently NaN for non-front-month futures (Yahoo does not populate
        regularMarketPrice in the quote API for back months).  Kept only as
        a last-resort fallback.

    Returns None if all three tiers fail.  Never raises.
    """
    if not _YF_AVAILABLE:
        return None

    ticker_obj = yf.Ticker(symbol)

    # Tier 1: explicit date-range history — the correct call for back-month futures.
    # period= shorthands fail because Yahoo's chart API maps them to relative
    # timestamps that are rejected for specific-expiry contract symbols.
    # Explicit start/end bypasses this restriction.
    try:
        end_dt   = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=30)
        hist = ticker_obj.history(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            interval="1d",
        )
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            price = _safe_positive_float(closes.iloc[-1]) if len(closes) >= 1 else None
            if price is not None:
                log.debug("curve tier1 (explicit-range history) OK for %s: %.4f", symbol, price)
                return round(price, 6)
        log.debug("curve tier1 (explicit-range history) empty for %s", symbol)
    except Exception as exc:
        log.debug("curve tier1 (explicit-range history) failed for %s: %s", symbol, exc)

    # Tier 2: quoteSummary regularMarketPrice — works for actively-traded back months.
    try:
        info  = ticker_obj.info
        price = _safe_positive_float(info.get("regularMarketPrice"))
        if price is not None:
            log.debug("curve tier2 (info.regularMarketPrice) OK for %s: %.4f", symbol, price)
            return round(price, 6)
        log.debug("curve tier2 (info.regularMarketPrice) missing/zero for %s", symbol)
    except Exception as exc:
        log.debug("curve tier2 (info.regularMarketPrice) failed for %s: %s", symbol, exc)

    # Tier 3: quote API fast_info — last resort; often NaN for back-month futures.
    try:
        price = _safe_positive_float(ticker_obj.fast_info.last_price)
        if price is not None:
            log.debug("curve tier3 (fast_info.last_price) OK for %s: %.4f", symbol, price)
            return round(price, 6)
        log.debug("curve tier3 (fast_info.last_price) NaN/zero for %s", symbol)
    except Exception as exc:
        log.debug("curve tier3 (fast_info.last_price) failed for %s: %s", symbol, exc)

    log.warning("curve: all tiers failed for %s — symbol may be unlisted in Yahoo Finance", symbol)
    return None


def _fetch_chain_prices(
    symbols: list[tuple[str, str]]
) -> dict[str, float | None]:
    """Fetch prices for a list of (symbol, label) contract pairs.

    REPLACEABLE: to swap the data source, replace this function body only.
    The rest of get_curve() is source-agnostic.

    Returns: dict mapping symbol -> price (None if unavailable).
    Source label: "delayed" (yfinance ~15-min delayed).

    Uses a bounded thread pool to parallelise yfinance calls without
    triggering rate-limit bans (max 4 concurrent requests).
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
          "source":          "delayed",
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
    log.debug("curve symbols for %s: %s", key, [s for s, _ in symbols])
    prices = _fetch_chain_prices(symbols)

    contracts = [
        {
            "symbol": sym,
            "label":  label,
            "price":  prices.get(sym),
            # "delayed" = ~15-min delayed Yahoo Finance data (not settlement)
            "status": "delayed" if prices.get(sym) is not None else "unavailable",
        }
        for sym, label in symbols
    ]

    # Analytics on the valid sub-set
    valid = [c for c in contracts if c["price"] is not None]
    log.debug("curve: %d/%d contracts priced for %s", len(valid), len(contracts), key)

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
        # Honest label: Yahoo Finance data is ~15-min delayed, not live or settlement.
        "source":           _CURVE_SOURCE,
        "ts":               ts,
        "error":            None if valid else (
            f"No contract prices returned from {CURVE_PROVIDER} for any of the "
            f"{len(contracts)} generated symbols — check symbol format or provider availability"
        ),
    }

    with _curve_lock:
        _curve_cache[key] = {"data": result, "ts": time.monotonic()}

    return result

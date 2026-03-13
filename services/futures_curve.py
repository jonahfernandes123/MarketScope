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

Fetch strategy for back-month futures (why Ticker.history() fails):
  Yahoo Finance's /v8/finance/chart API endpoint serves OHLCV data for
  specific-expiry futures contracts BUT yfinance's Ticker.history() wrapper
  applies additional validation/adjustment that rejects or discards the data
  for these symbols.  yf.download() uses a different internal code path that
  bypasses this validation and directly hits the Yahoo download endpoint,
  which reliably returns OHLCV for active futures contracts.

  The fix is:
    Tier 1 — yf.download() with period="1mo".
              More reliable than Ticker.history() for specific-expiry futures.
              Handles MultiIndex DataFrame output when downloading a single
              symbol and normalises it to a flat DataFrame before extracting
              the last Close price.
    Tier 2 — Ticker.history(period="1mo").
              Fallback in case yf.download() fails for a given symbol.
              Uses period= (not explicit dates) as the explicit date approach
              also exhibits the same validation issues.
    Tier 3 — info.get("regularMarketPrice").
              Yahoo /v10/finance/quoteSummary; slower but often populated
              for actively-traded back-month futures when chart endpoints fail.
"""

from __future__ import annotations

import concurrent.futures
import logging
import math
import threading
import time
from datetime import datetime, timezone

try:
    import pandas as pd
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

      Tier 1: yf.download() with period="1mo".
        Uses a different internal code path than Ticker.history() and bypasses
        the validation/adjustment that causes Ticker.history() to return empty
        DataFrames for specific-expiry back-month futures (e.g. CLJ26=F).
        yf.download() for a single symbol returns a MultiIndex DataFrame;
        column level 0 is normalised away before extracting the last Close.

      Tier 2: Ticker.history(period="1mo").
        Fallback for cases where yf.download() fails.  Uses period= rather
        than explicit dates — the explicit date approach exhibited the same
        issues as the old Ticker.history() calls.

      Tier 3: info.get("regularMarketPrice").
        Yahoo /v10/finance/quoteSummary; slower but often populated for
        actively-traded back-month futures when both chart endpoints fail.

    Returns None if all three tiers fail.  Never raises.
    """
    if not _YF_AVAILABLE:
        return None

    # Tier 1: yf.download() — more reliable than Ticker.history() for specific-expiry futures.
    try:
        df = yf.download(
            symbol,
            period="1mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if df is not None and not df.empty:
            # yf.download() returns a MultiIndex DataFrame when downloading one symbol.
            # Normalise to a flat DataFrame by dropping the outer ticker level.
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            closes = df["Close"].dropna() if "Close" in df.columns else pd.Series()
            price = _safe_positive_float(closes.iloc[-1]) if len(closes) >= 1 else None
            if price is not None:
                log.debug("curve tier1 (download) OK for %s: %.4f", symbol, price)
                return round(price, 6)
        log.debug("curve tier1 (download) empty for %s", symbol)
    except Exception as exc:
        log.debug("curve tier1 (download) failed for %s: %s", symbol, exc)

    # Tier 2: Ticker.history(period="1mo") — fallback when yf.download() fails.
    try:
        ticker_obj = yf.Ticker(symbol)
        hist = ticker_obj.history(period="1mo", interval="1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            price = _safe_positive_float(closes.iloc[-1]) if len(closes) >= 1 else None
            if price is not None:
                log.debug("curve tier2 (Ticker.history period) OK for %s: %.4f", symbol, price)
                return round(price, 6)
        log.debug("curve tier2 (Ticker.history period) empty for %s", symbol)
    except Exception as exc:
        log.debug("curve tier2 (Ticker.history period) failed for %s: %s", symbol, exc)

    # Tier 3: quoteSummary regularMarketPrice — last resort.
    try:
        ticker_obj = yf.Ticker(symbol)
        info  = ticker_obj.info
        price = _safe_positive_float(info.get("regularMarketPrice"))
        if price is not None:
            log.debug("curve tier3 (info.regularMarketPrice) OK for %s: %.4f", symbol, price)
            return round(price, 6)
        log.debug("curve tier3 (info.regularMarketPrice) missing/zero for %s", symbol)
    except Exception as exc:
        log.debug("curve tier3 (info.regularMarketPrice) failed for %s: %s", symbol, exc)

    log.warning("curve: all tiers failed for %s — symbol may be unlisted in Yahoo Finance", symbol)
    return None


def _bulk_download(symbols: list[str]) -> dict[str, float | None]:
    """Attempt to fetch all symbols in one yf.download() call.

    More efficient than individual calls and avoids per-symbol rate limits.
    Returns a dict mapping symbol -> price (or None).
    """
    try:
        symbols_str = " ".join(symbols)
        df = yf.download(
            symbols_str,
            period="1mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="ticker",
        )
        if df is None or df.empty:
            return {}
        result = {}
        for sym in symbols:
            try:
                if isinstance(df.columns, pd.MultiIndex) and sym in df.columns.get_level_values(0):
                    closes = df[sym]["Close"].dropna()
                else:
                    closes = pd.Series()
                price = _safe_positive_float(closes.iloc[-1]) if len(closes) >= 1 else None
                result[sym] = price
            except Exception:
                result[sym] = None
        return result
    except Exception as exc:
        log.debug("bulk download failed: %s", exc)
        return {}


def _fetch_chain_prices(
    symbols: list[tuple[str, str]]
) -> dict[str, float | None]:
    """Fetch prices for a list of (symbol, label) contract pairs.

    REPLACEABLE: to swap the data source, replace this function body only.
    The rest of get_curve() is source-agnostic.

    Returns: dict mapping symbol -> price (None if unavailable).
    Source label: "delayed" (yfinance ~15-min delayed).

    Strategy:
      1. Attempt a single bulk yf.download() for all symbols at once —
         more efficient and avoids per-symbol rate limits.
      2. For any symbols that returned None from the bulk call, fall back to
         individual _fetch_yf_price() calls via a bounded thread pool
         (max_workers=2 to avoid Yahoo Finance rate-limiting).
    """
    sym_list = [sym for sym, _ in symbols]

    # Step 1: bulk download attempt
    prices: dict[str, float | None] = {}
    if _YF_AVAILABLE:
        log.debug("curve: attempting bulk download for %d symbols", len(sym_list))
        bulk = _bulk_download(sym_list)
        prices.update(bulk)
        got = sum(1 for v in bulk.values() if v is not None)
        log.debug("curve: bulk download returned %d/%d prices", got, len(sym_list))

    # Step 2: individual fallback for symbols not priced by the bulk call
    missing = [sym for sym in sym_list if prices.get(sym) is None]
    if missing:
        log.debug("curve: individual fallback for %d symbols", len(missing))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            fut_map = {pool.submit(_fetch_yf_price, sym): sym for sym in missing}
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

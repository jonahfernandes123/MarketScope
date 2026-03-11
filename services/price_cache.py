from __future__ import annotations

import concurrent.futures
import threading
import time
from datetime import datetime, timezone

from models.instruments import INSTRUMENTS


# ── Shared cache ─────────────────────────────────────────────────────────────────

_price_data: dict[str, dict] = {}
_cache_lock = threading.Lock()

# ── Refresh deduplication ─────────────────────────────────────────────────────────
# Prevents concurrent refresh calls (e.g. startup + background loop overlap) from
# both hammering upstream APIs simultaneously.

_refresh_running = threading.Event()   # set = refresh in progress


# ── Per-instrument update ────────────────────────────────────────────────────────

def _update_instrument(inst: dict) -> None:
    """Fetch one instrument's price and update the shared cache (thread-safe).

    On success: stores price and previous day's close (prev_price) for 24h change.
    On error:   keeps the last known values so the UI stays populated.
    """
    key = inst["key"]
    try:
        result = inst["fetch"]()
        if isinstance(result, tuple) and len(result) == 3:
            new_price, new_prev, new_changes = result
        elif isinstance(result, tuple):
            new_price, new_prev = result
            new_changes = {}
        else:
            new_price, new_prev, new_changes = result, None, {}
        error = None
    except Exception as exc:
        new_price   = None
        new_prev    = None
        new_changes = {}
        error = str(exc)[:100]

    with _cache_lock:
        cached = _price_data.get(key, {})
        ts = datetime.now(timezone.utc).isoformat()
        if error is None:
            _price_data[key] = {
                "price":       new_price,
                "prev_price":  new_prev if new_prev is not None else cached.get("prev_price"),
                "change_1d":   new_changes.get("change_1d"),
                "change_1w":   new_changes.get("change_1w"),
                "change_1mo":  new_changes.get("change_1mo"),
                "change_1y":   new_changes.get("change_1y"),
                "error":       None,
                "ts":          ts,
            }
        else:
            _price_data[key] = {
                "price":       cached.get("price"),
                "prev_price":  cached.get("prev_price"),
                "change_1d":   cached.get("change_1d"),
                "change_1w":   cached.get("change_1w"),
                "change_1mo":  cached.get("change_1mo"),
                "change_1y":   cached.get("change_1y"),
                "error":       error,
                "ts":          ts,
            }


def refresh_prices() -> None:
    """Refresh all instrument prices.

    No-op if a refresh is already running (deduplication guard).
    Limits concurrent upstream calls to 6 workers to avoid 429 storms.
    """
    if _refresh_running.is_set():
        return
    _refresh_running.set()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futs = [pool.submit(_update_instrument, inst) for inst in INSTRUMENTS]
            concurrent.futures.wait(futs)
    finally:
        _refresh_running.clear()


def _background_loop(refresh_seconds: int) -> None:
    while True:
        time.sleep(refresh_seconds)
        refresh_prices()

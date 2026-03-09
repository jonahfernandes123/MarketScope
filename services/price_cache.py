from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from models.instruments import INSTRUMENTS


# ── Shared cache ─────────────────────────────────────────────────────────────────

_price_data: dict[str, dict] = {}
_cache_lock = threading.Lock()


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
    threads = [threading.Thread(target=_update_instrument, args=(inst,), daemon=True)
               for inst in INSTRUMENTS]
    for t in threads: t.start()
    for t in threads: t.join()


def _background_loop(refresh_seconds: int) -> None:
    while True:
        time.sleep(refresh_seconds)
        refresh_prices()

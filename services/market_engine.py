from __future__ import annotations

import concurrent.futures
import threading
import time
from datetime import datetime, timezone

from models.instruments import INSTRUMENTS


class MarketEngine:
    """Central price cache and refresh engine.

    Single source of truth for all instrument prices.  Thread-safe.
    Handles refresh deduplication, per-provider source tagging, and
    stale-value preservation on upstream errors.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._lock  = threading.Lock()
        self._busy  = threading.Event()   # set while a refresh is in progress

    # ── Public API ───────────────────────────────────────────────────────────

    def get_snapshot(self) -> dict[str, dict]:
        """Return a shallow copy of the full cache (non-blocking)."""
        with self._lock:
            return dict(self._cache)

    def get_entry(self, key: str) -> dict:
        """Return the cache entry for a single instrument key."""
        with self._lock:
            return dict(self._cache.get(key, {}))

    @property
    def is_refreshing(self) -> bool:
        return self._busy.is_set()

    def refresh_all(self) -> None:
        """Fetch all instrument prices concurrently.

        No-op when a refresh is already running (deduplication guard).
        Caps concurrent upstream calls at 6 workers to avoid rate-limit storms.
        """
        if self._busy.is_set():
            return
        self._busy.set()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                futs = [pool.submit(self._update_one, inst) for inst in INSTRUMENTS]
                concurrent.futures.wait(futs)
        finally:
            self._busy.clear()

    def start(self, interval_seconds: int) -> None:
        """Blocking initial refresh, then launch a daemon background loop."""
        self.refresh_all()
        threading.Thread(
            target=self._background_loop,
            args=(interval_seconds,),
            daemon=True,
            name="market-engine-bg",
        ).start()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _update_one(self, inst: dict) -> None:
        key      = inst["key"]
        provider = inst.get("provider", "yfinance")
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
            new_price = new_prev = None
            new_changes = {}
            error = str(exc)[:120]

        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cached = self._cache.get(key, {})
            if error is None:
                self._cache[key] = {
                    "price":      new_price,
                    "prev_price": new_prev if new_prev is not None else cached.get("prev_price"),
                    "change_1d":  new_changes.get("change_1d"),
                    "change_1w":  new_changes.get("change_1w"),
                    "change_1mo": new_changes.get("change_1mo"),
                    "change_1y":  new_changes.get("change_1y"),
                    "error":      None,
                    "stale":      False,
                    "source":     provider,
                    "ts":         ts,
                }
            else:
                # Keep last-known-good values; flag as stale so UI knows
                self._cache[key] = {
                    "price":      cached.get("price"),
                    "prev_price": cached.get("prev_price"),
                    "change_1d":  cached.get("change_1d"),
                    "change_1w":  cached.get("change_1w"),
                    "change_1mo": cached.get("change_1mo"),
                    "change_1y":  cached.get("change_1y"),
                    "error":      error,
                    "stale":      cached.get("price") is not None,
                    "source":     cached.get("source"),
                    "ts":         ts,
                }

    def _background_loop(self, interval: int) -> None:
        while True:
            time.sleep(interval)
            self.refresh_all()


# ── Module-level singleton ────────────────────────────────────────────────────
engine = MarketEngine()

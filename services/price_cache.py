"""Backward-compatibility shim — all logic now lives in services.market_engine."""
from services.market_engine import engine

# Legacy names still importable from external code
_cache_lock = engine._lock
_price_data = engine._cache


def refresh_prices() -> None:
    engine.refresh_all()


def _background_loop(interval: int) -> None:
    engine._background_loop(interval)

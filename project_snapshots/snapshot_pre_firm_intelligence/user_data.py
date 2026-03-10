"""
services/user_data.py
---------------------
Isolated read/write layer for per-user private workspace data.

All functions take `username` as their first argument and operate only on
that user's slice of the data — no cross-user access is possible.

Storage format (data/user_data.json):
{
  "Noah": {
    "vitol": { "notes": "", "contacts": [] },
    "glencore": { "notes": "", "contacts": [] }
  }
}

To swap the backend from JSON to a database later, only this file needs
to change — the API routes and callers remain the same.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from config import USER_DATA_PATH

_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    """Read the full data file. Returns {} if missing or corrupt."""
    if not os.path.exists(USER_DATA_PATH):
        return {}
    try:
        with open(USER_DATA_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    """Write the full data file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(USER_DATA_PATH), exist_ok=True)
    with open(USER_DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_firms(username: str) -> dict[str, dict]:
    """Return all firm entries for the given user."""
    with _lock:
        return dict(_load().get(username, {}))


def get_firm_entry(username: str, firm_key: str) -> dict[str, Any]:
    """Return one firm's private workspace data for the user.

    Always returns a valid structure even if the entry doesn't exist yet.
    """
    with _lock:
        data = _load()
    return data.get(username, {}).get(firm_key, {"notes": "", "contacts": []})


def save_firm_entry(username: str, firm_key: str, entry: dict[str, Any]) -> None:
    """Write one firm's private workspace data for the user.

    Only 'notes' (str) and 'contacts' (list) are persisted; unknown keys
    are dropped to keep the file clean.
    """
    with _lock:
        data = _load()
        if username not in data:
            data[username] = {}
        data[username][firm_key] = {
            "notes":    str(entry.get("notes", "")),
            "contacts": list(entry.get("contacts", [])),
        }
        _save(data)


def get_user_password(username: str) -> str | None:
    """Return the stored password override for the user, or None if unchanged."""
    with _lock:
        return _load().get(username, {}).get("_password")


def save_user_password(username: str, password: str) -> None:
    """Persist a new password for the user, overriding the config default."""
    with _lock:
        data = _load()
        if username not in data:
            data[username] = {}
        data[username]["_password"] = password
        _save(data)


def get_favorite_firms(username: str) -> list[str]:
    """Return the user's list of favorited firm keys."""
    with _lock:
        return list(_load().get(username, {}).get("_favorite_firms", []))


def save_favorite_firms(username: str, keys: list[str]) -> None:
    """Persist the user's list of favorited firm keys."""
    with _lock:
        data = _load()
        if username not in data:
            data[username] = {}
        data[username]["_favorite_firms"] = [str(k) for k in keys]
        _save(data)


def ensure_user_initialized(username: str) -> None:
    """Create an empty top-level entry for the user if one doesn't exist.

    Called at login so the JSON file always has a record for every user
    who has logged in, even before they create any notes.
    """
    with _lock:
        data = _load()
        if username not in data:
            data[username] = {}
            _save(data)

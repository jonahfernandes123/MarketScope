"""
services/user_data.py
---------------------
Per-user persistent storage backed by Postgres (production) or SQLite (local dev).

Schema — single table `user_data`:
  username  TEXT   NOT NULL
  firm_key  TEXT   NOT NULL   (use '_password' / '_favorites' for special rows)
  notes     TEXT
  contacts  TEXT   (JSON array)
  PRIMARY KEY (username, firm_key)

Special firm_key values:
  _password  — stores password override in `notes` column
  _favorites — stores JSON-encoded list of firm keys in `notes` column
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from typing import Any

import config

# ── Driver selection ──────────────────────────────────────────────────────────

_DB_URL = config.DATABASE_URL

if _DB_URL:
    # Render / Heroku sometimes supply "postgres://" — psycopg2 needs "postgresql://"
    if _DB_URL.startswith("postgres://"):
        _DB_URL = "postgresql://" + _DB_URL[len("postgres://"):]
    import psycopg2
    import psycopg2.pool
    _BACKEND = "pg"
    _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, _DB_URL)

    @contextmanager
    def _conn():
        conn = _pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _pool.putconn(conn)

    def _execute(sql: str, params=()) -> list:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            try:
                return cur.fetchall()
            except Exception:
                return []

    _PH = "%s"

else:
    # Local dev fallback — SQLite (no extra install needed)
    import sqlite3
    _BACKEND = "sqlite"
    _sqlite_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "user_data.sqlite"
    )
    os.makedirs(os.path.dirname(_sqlite_path), exist_ok=True)
    _sqlite_lock = threading.Lock()

    @contextmanager
    def _conn():
        with _sqlite_lock:
            conn = sqlite3.connect(_sqlite_path)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _execute(sql: str, params=()) -> list:
        with _conn() as conn:
            cur = conn.execute(sql, params)
            try:
                return cur.fetchall()
            except Exception:
                return []

    _PH = "?"


# ── Schema init ───────────────────────────────────────────────────────────────

def _init_schema() -> None:
    ddl = """
        CREATE TABLE IF NOT EXISTS user_data (
            username  TEXT NOT NULL,
            firm_key  TEXT NOT NULL,
            notes     TEXT NOT NULL DEFAULT '',
            contacts  TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (username, firm_key)
        )
    """
    with _conn() as conn:
        if _BACKEND == "pg":
            conn.cursor().execute(ddl)
        else:
            conn.execute(ddl)

_init_schema()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _upsert(username: str, firm_key: str, notes: str, contacts: str) -> None:
    if _BACKEND == "pg":
        _execute(
            f"""
            INSERT INTO user_data (username, firm_key, notes, contacts)
            VALUES ({_PH}, {_PH}, {_PH}, {_PH})
            ON CONFLICT (username, firm_key) DO UPDATE
              SET notes = EXCLUDED.notes, contacts = EXCLUDED.contacts
            """,
            (username, firm_key, notes, contacts),
        )
    else:
        _execute(
            f"""
            INSERT INTO user_data (username, firm_key, notes, contacts)
            VALUES ({_PH}, {_PH}, {_PH}, {_PH})
            ON CONFLICT (username, firm_key) DO UPDATE
              SET notes = excluded.notes, contacts = excluded.contacts
            """,
            (username, firm_key, notes, contacts),
        )


def _get(username: str, firm_key: str) -> tuple | None:
    rows = _execute(
        f"SELECT notes, contacts FROM user_data WHERE username = {_PH} AND firm_key = {_PH}",
        (username, firm_key),
    )
    return rows[0] if rows else None


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_firms(username: str) -> dict[str, dict]:
    """Return all firm entries for the given user (excludes special _ rows)."""
    if _BACKEND == "pg":
        rows = _execute(
            f"SELECT firm_key, notes, contacts FROM user_data WHERE username = {_PH} AND firm_key NOT LIKE '\\_%%' ESCAPE '\\'",
            (username,),
        )
    else:
        rows = _execute(
            f"SELECT firm_key, notes, contacts FROM user_data WHERE username = {_PH} AND firm_key NOT LIKE '\\_%%' ESCAPE '\\'",
            (username,),
        )
    result = {}
    for firm_key, notes, contacts_json in rows:
        try:
            contacts = json.loads(contacts_json)
        except (json.JSONDecodeError, TypeError):
            contacts = []
        result[firm_key] = {"notes": notes, "contacts": contacts}
    return result


def get_firm_entry(username: str, firm_key: str) -> dict[str, Any]:
    """Return one firm's workspace data; returns empty structure if not found."""
    row = _get(username, firm_key)
    if not row:
        return {"notes": "", "contacts": []}
    notes, contacts_json = row
    try:
        contacts = json.loads(contacts_json)
    except (json.JSONDecodeError, TypeError):
        contacts = []
    return {"notes": notes, "contacts": contacts}


def save_firm_entry(username: str, firm_key: str, entry: dict[str, Any]) -> None:
    """Write one firm's workspace data for the user."""
    notes    = str(entry.get("notes", ""))
    contacts = json.dumps(list(entry.get("contacts", [])), ensure_ascii=False)
    _upsert(username, firm_key, notes, contacts)


def get_user_password(username: str) -> str | None:
    """Return the stored password override, or None if unchanged."""
    row = _get(username, "_password")
    return row[0] if row else None


def save_user_password(username: str, password: str) -> None:
    """Persist a new password for the user."""
    _upsert(username, "_password", password, "[]")


def get_favorite_firms(username: str) -> list[str]:
    """Return the user's list of favorited firm keys."""
    row = _get(username, "_favorites")
    if not row:
        return []
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return []


def save_favorite_firms(username: str, keys: list[str]) -> None:
    """Persist the user's list of favorited firm keys."""
    _upsert(username, "_favorites", json.dumps([str(k) for k in keys], ensure_ascii=False), "[]")


def ensure_user_initialized(username: str) -> None:
    """No-op — rows are created on demand."""
    pass

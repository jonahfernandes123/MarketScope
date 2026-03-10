"""
config.py
---------
Central configuration for Market Dashboard.
All sensitive values are read from environment variables.

DEPLOYMENT CHECKLIST
--------------------
  SECRET_KEY      — REQUIRED. Set to a long random string (e.g. `openssl rand -hex 32`).
                    If absent, the server refuses to start in production mode.
  DASHBOARD_USERS — Optional. Override credentials via JSON env var.
                    e.g.  DASHBOARD_USERS='{"Noah": "password123"}'
  USER_DATA_PATH  — Optional. Absolute path to the user_data.json file.
                    Must point to a persistent volume in cloud deployments.
"""

from __future__ import annotations

import json
import os
import warnings

# ── Production flag ───────────────────────────────────────────────────────────
# True when SECRET_KEY env var is present (i.e. a real deployment).
# Controls SESSION_COOKIE_SECURE and whether the insecure dev key is allowed.
PRODUCTION: bool = bool(os.environ.get("SECRET_KEY", "").strip())


# ── Secret key ────────────────────────────────────────────────────────────────
_secret_env = os.environ.get("SECRET_KEY", "").strip()

if _secret_env:
    SECRET_KEY: str = _secret_env
else:
    # ⚠ DEV-ONLY FALLBACK — never acceptable for a public/deployed server.
    # Sessions signed with this key can be forged by anyone who reads this file.
    SECRET_KEY = "dev-only-insecure-key-CHANGE-BEFORE-DEPLOY-xK9mQ2p"
    warnings.warn(
        "\n"
        "  ┌─────────────────────────────────────────────────────┐\n"
        "  │  WARNING: SECRET_KEY not set.                       │\n"
        "  │  Using insecure dev default — DO NOT deploy this.   │\n"
        "  │  Set the SECRET_KEY environment variable first.     │\n"
        "  └─────────────────────────────────────────────────────┘",
        stacklevel=2,
    )


# ── Users ─────────────────────────────────────────────────────────────────────
# To override via environment (recommended for deployment):
#   DASHBOARD_USERS='{"Noah": "password123", "Jonah": "otherpass"}'
_users_env = os.environ.get("DASHBOARD_USERS", "").strip()
if _users_env:
    try:
        USERS: dict[str, str] = json.loads(_users_env)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "DASHBOARD_USERS env var must be valid JSON, "
            'e.g. \'{"Noah": "pass123"}\''
        ) from exc
else:
    # Default credentials — override via DASHBOARD_USERS env var in production.
    USERS = {
        "Noah":  "JonahandNoah",
        "Jonah": "JonahandNoah",
    }


# ── Per-user data file ────────────────────────────────────────────────────────
# In cloud deployments, set USER_DATA_PATH to a path on a persistent volume.
# e.g.  USER_DATA_PATH=/data/user_data.json
USER_DATA_PATH: str = os.environ.get(
    "USER_DATA_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "user_data.json"),
)

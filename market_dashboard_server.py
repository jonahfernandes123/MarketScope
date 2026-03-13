# THIS IS THE ACTIVE MARKET DASHBOARD SERVER
"""
market_snapshot_web.py
----------------------
Web-based market dashboard with interactive charts, live news, and macro analysis.
Runs at http://localhost:5000

Data sources (all free, no API key required):
  - Bitcoin       : CoinGecko public API (price) + yfinance (history)
  - EUR/USD       : Frankfurter.app (price + monthly/yearly history)
  - Gold, Silver, Copper, Brent, Henry Hub, TTF Gas : Yahoo Finance (yfinance)
  - News & Context: Yahoo Finance news + Google News RSS

Requirements:
  pip install flask requests yfinance
"""

from __future__ import annotations

import concurrent.futures
import uuid
from datetime import datetime, timezone
from functools import wraps

import config
from flask import (
    Flask, jsonify, redirect, render_template,
    request as freq, session, url_for,
)

from models.instruments import CONTEXT_QUERIES, INSTRUMENT_MAP, INSTRUMENTS, SUMMARIES
from services.market_data import YFINANCE_AVAILABLE, _history_bitcoin, _history_ethereum, _history_eurusd, _history_yf
from services.market_engine import engine
from services.futures_curve import get_curve
from services.news_fetcher import _fetch_context_news, _fetch_news_for_query, _fetch_yf_news
from services.user_data import (
    ensure_user_initialized, get_firm_entry, save_firm_entry,
    get_user_password, save_user_password,
    get_favorite_firms, save_favorite_firms,
    get_user_firms,
)

app = Flask(__name__)
REFRESH_SECONDS = 30

# ── Server-side session nonces ─────────────────────────────────────────────────
# Cleared on every server restart → all existing cookies become invalid.
_valid_sessions: set[str] = set()

# ── Session / security config ─────────────────────────────────────────────────
app.secret_key = config.SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"]  = True
app.config["SESSION_COOKIE_SAMESITE"]  = "Lax"
# SESSION_COOKIE_SECURE requires HTTPS — only enabled when SECRET_KEY env var
# is set, which is the signal that this is a production/deployed environment.
app.config["SESSION_COOKIE_SECURE"]    = config.PRODUCTION
# No persistent session — cookie expires when the browser closes


# ── Security headers ──────────────────────────────────────────────────────────

@app.after_request
def _set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    return response


# ── Auth helpers ──────────────────────────────────────────────────────────────

def login_required(f):
    """Guard page routes (redirect) and API routes (401 JSON)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        nonce = session.get("nonce")
        if "user" not in session or nonce not in _valid_sessions:
            if freq.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized", "login": True}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Login / Logout ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if freq.method == "GET":
        _valid_sessions.discard(session.get("nonce"))  # Invalidate any previous session
        session.clear()

    error = None
    prefill_username = ""

    if freq.method == "POST":
        username = freq.form.get("username", "").strip()
        password = freq.form.get("password", "")

        # Stored password (set via change-password) overrides the config default.
        stored_pw = get_user_password(username)
        expected  = stored_pw if stored_pw is not None else config.USERS.get(username)
        if username in config.USERS and expected == password:
            nonce = str(uuid.uuid4())
            _valid_sessions.add(nonce)
            session["user"] = username
            session["nonce"] = nonce
            ensure_user_initialized(username)
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password."
            prefill_username = username

    return render_template("login.html", error=error, prefill_username=prefill_username)


@app.route("/logout")
def logout():
    _valid_sessions.discard(session.get("nonce"))
    session.clear()
    return redirect(url_for("login"))


# ── API routes ─────────────────────────────────────────────────────────────────

def _price_status(inst: dict, d: dict) -> str:
    """Compute a data-quality status string for one instrument snapshot entry.

    Status values:
      live        — Real-time feed (Binance; sub-second latency)
      delayed     — ~15-minute delayed market data (yfinance intraday)
      settlement  — Official daily settlement / fixing (Frankfurter ECB rate)
      unavailable — No price data at all (cold start or persistent error)
    """
    if d.get("price") is None:
        return "unavailable"
    if d.get("stale"):
        return "delayed"   # serving cached value; upstream refresh failed
    provider = inst.get("provider", "yfinance")
    if provider == "binance":
        return "live"
    # Frankfurter is the ECB daily fixing; yfinance FX/futures are ~15 min delayed.
    # Both are labelled "delayed" because we primarily use yfinance intraday even for
    # EUR/USD — the Frankfurter fallback would be "settlement" but we can't distinguish
    # at this layer without changing the fetch return signature.
    return "delayed"


@app.route("/api/prices")
@login_required
def api_prices():
    snapshot = engine.get_snapshot()
    result = []
    for inst in INSTRUMENTS:
        d = snapshot.get(inst["key"], {})
        result.append({
            "key": inst["key"], "label": inst["label"],
            "price": d.get("price"), "prev_price": d.get("prev_price"),
            "change_1d":  d.get("change_1d"),
            "change_1w":  d.get("change_1w"),
            "change_1mo": d.get("change_1mo"),
            "change_1y":  d.get("change_1y"),
            "error": d.get("error"),
            "stale": d.get("stale", False),
            "source": d.get("source"),
            "ts": d.get("ts"),
            "prefix": inst["prefix"], "suffix": inst["suffix"],
            "decimals": inst["decimals"], "thousands": inst["thousands"],
            "icon": inst["icon"], "accent": inst["accent"],
            # ── Price model metadata ──────────────────────────────────────────
            "asset_class":    inst.get("asset_class", "other"),
            "price_type":     inst.get("price_type", "futures"),
            "spot_available": inst.get("spot_available", False),
            "contract_label": inst.get("contract_label"),
            "curve_enabled":  inst.get("curve_enabled", False),
            "price_status":   _price_status(inst, d),
        })
    return jsonify(result)


@app.route("/api/history/<key>")
@login_required
def api_history(key: str):
    inst = INSTRUMENT_MAP.get(key)
    if not inst:
        return jsonify({"error": "Unknown instrument"}), 404
    range_param = freq.args.get("range", "1mo")
    if range_param not in ("1d", "1w", "1mo", "1y"):
        range_param = "1mo"
    try:
        if key == "bitcoin":
            data = _history_bitcoin(range_param)
        elif key == "ethereum":
            data = _history_ethereum(range_param)
        elif key == "eurusd":
            data = _history_eurusd(range_param)
        elif inst["ticker"]:
            data = _history_yf(inst["ticker"], range_param)
        else:
            return jsonify({"error": "No history source configured"}), 500
        data.update({
            "label": inst["label"], "prefix": inst["prefix"],
            "suffix": inst["suffix"], "decimals": inst["decimals"],
            "thousands": inst["thousands"], "accent": inst["accent"],
        })
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/curve/<key>")
@login_required
def api_curve(key: str):
    """Return the futures forward curve (term structure) for one instrument.

    Uses a 5-minute server-side cache.  Only instruments with curve_enabled=True
    in instruments.py will return meaningful data; others return an empty contract
    list with curve_state="insufficient".
    """
    inst = INSTRUMENT_MAP.get(key)
    if not inst:
        return jsonify({"error": "Unknown instrument"}), 404
    try:
        data = get_curve(inst)
        # Attach display-formatting fields so the frontend can render prices
        data["prefix"]    = inst["prefix"]
        data["suffix"]    = inst["suffix"]
        data["decimals"]  = inst["decimals"]
        data["thousands"] = inst["thousands"]
        data["label"]     = inst["label"]
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# TODO: REMOVE THIS DEBUG ENDPOINT before going to production.
# Temporary diagnostic route — requires login, returns raw tier-by-tier
# fetch results for every contract symbol in one instrument's curve chain.
# Usage: GET /api/curve/debug/<instrument_key>
# Example: /api/curve/debug/wti  or  /api/curve/debug/gold
@app.route("/api/curve/debug/<key>")
@login_required
def api_curve_debug(key: str):
    """DEBUG/TEMP: Per-symbol, per-tier fetch report for one instrument's curve chain.

    For each generated contract symbol the response includes:
      - symbol    : the yfinance ticker string (e.g. CLJ26=F)
      - label     : human-readable expiry label (e.g. "Apr 2026")
      - tier1_5d  : price from history(period="5d") via shared cache, or null
      - tier2_1mo : price from history(period="1mo") direct, or null
      - tier3_fi  : price from fast_info.last_price, or null
      - final     : the price _fetch_yf_price() would return (first non-null tier)
      - error     : error string if all tiers failed, else null

    Source label: delayed (~15-min delayed Yahoo Finance data)
    """
    import math

    inst = INSTRUMENT_MAP.get(key)
    if not inst:
        return jsonify({"error": "Unknown instrument"}), 404
    if not inst.get("curve_enabled"):
        return jsonify({"error": f"curve_enabled=False for {key}"}), 400

    from services.futures_curve import _upcoming_contracts
    from services.market_data import _yf_fetch, YFINANCE_AVAILABLE

    if not YFINANCE_AVAILABLE:
        return jsonify({"error": "yfinance not installed"}), 500

    try:
        import yfinance as yf
    except ImportError:
        return jsonify({"error": "yfinance not installed"}), 500

    root   = inst["curve_root"]
    months = inst["curve_months"]
    n      = inst.get("curve_n", 8)

    symbols = _upcoming_contracts(root, months, n=n)

    def _safe_float(val) -> float | None:
        """Return float or None; treats NaN and non-positive as None."""
        try:
            f = float(val)
            if math.isnan(f) or f <= 0:
                return None
            return round(f, 6)
        except Exception:
            return None

    def _tier1(sym: str) -> tuple[float | None, str | None]:
        try:
            hist = _yf_fetch(sym, "5d", "1d")
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if len(closes) >= 1:
                    return _safe_float(closes.iloc[-1]), None
            return None, "empty or no data"
        except Exception as exc:
            return None, str(exc)

    def _tier2(sym: str) -> tuple[float | None, str | None]:
        try:
            hist = yf.Ticker(sym).history(period="1mo", interval="1d")
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if len(closes) >= 1:
                    return _safe_float(closes.iloc[-1]), None
            return None, "empty or no data"
        except Exception as exc:
            return None, str(exc)

    def _tier3(sym: str) -> tuple[float | None, str | None]:
        try:
            price = yf.Ticker(sym).fast_info.last_price
            v = _safe_float(price)
            if v is not None:
                return v, None
            return None, f"raw value={price!r} (NaN or non-positive)"
        except Exception as exc:
            return None, str(exc)

    rows = []
    for sym, label in symbols:
        t1_price, t1_err = _tier1(sym)
        t2_price, t2_err = _tier2(sym)
        t3_price, t3_err = _tier3(sym)

        final = t1_price if t1_price is not None else (
            t2_price if t2_price is not None else t3_price
        )
        rows.append({
            "symbol":    sym,
            "label":     label,
            "tier1_5d":  {"price": t1_price, "error": t1_err},
            "tier2_1mo": {"price": t2_price, "error": t2_err},
            "tier3_fi":  {"price": t3_price, "error": t3_err},
            "final":     final,
            "error":     None if final is not None else "all tiers failed",
        })

    priced_count = sum(1 for r in rows if r["final"] is not None)
    return jsonify({
        "debug":        True,
        "source":       "delayed",
        "key":          key,
        "label":        inst["label"],
        "curve_root":   root,
        "curve_months": months,
        "curve_n":      n,
        "contracts":    rows,
        "priced":       priced_count,
        "total":        len(rows),
        "ts":           datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/summary/<key>")
@login_required
def api_summary(key: str):
    """Return static analysis + live news for one instrument."""
    s = SUMMARIES.get(key)
    if not s:
        return jsonify({"error": "No summary available"}), 404

    ticker = INSTRUMENT_MAP.get(key, {}).get("ticker", "")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_articles = pool.submit(_fetch_yf_news, ticker) if ticker else None
        f_context  = pool.submit(_fetch_context_news, key)
        articles = f_articles.result() if f_articles else []
        context  = f_context.result()

    return jsonify({
        "overview":     s["overview"],
        "macro":        s["macro"],
        "geopolitical": s["geopolitical"],
        "outlook":      s["outlook"],
        "articles":     articles,
        "context":      context,
    })


# ── Homepage API routes ─────────────────────────────────────────────────────────

@app.route("/api/home/movers")
@login_required
def api_home_movers():
    """Return all instruments ranked by absolute % change (largest first)."""
    snapshot = engine.get_snapshot()

    rows = []
    for inst in INSTRUMENTS:
        d = snapshot.get(inst["key"], {})
        price      = d.get("price")
        prev_price = d.get("prev_price")
        if price is not None and prev_price and prev_price != 0:
            pct = (price - prev_price) / prev_price * 100
        else:
            pct = None
        rows.append({
            "key":      inst["key"],
            "label":    inst["label"],
            "icon":     inst["icon"],
            "accent":   inst["accent"],
            "prefix":   inst["prefix"],
            "suffix":   inst["suffix"],
            "decimals": inst["decimals"],
            "thousands":inst["thousands"],
            "price":    price,
            "pct":      round(pct, 3) if pct is not None else None,
            "error":    d.get("error"),
        })

    rows.sort(key=lambda r: abs(r["pct"]) if r["pct"] is not None else -1, reverse=True)
    return jsonify(rows)


@app.route("/api/home/news")
@login_required
def api_home_news():
    """Aggregate the latest yfinance news across all instruments in parallel."""
    def _fetch(inst):
        return _fetch_yf_news(inst["ticker"]) if inst.get("ticker") else []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(INSTRUMENTS)) as pool:
        futures = {pool.submit(_fetch, inst): inst for inst in INSTRUMENTS}
        seen_urls = set()
        articles  = []
        for future in concurrent.futures.as_completed(futures):
            for article in (future.result() or [])[:2]:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    inst = futures[future]
                    articles.append({**article, "instrument": inst["label"],
                                     "accent": inst["accent"]})

    articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    return jsonify(articles)


_DRIVERS_QUERY = "global markets economy federal reserve inflation interest rates"

@app.route("/api/home/drivers")
@login_required
def api_home_drivers():
    """Fetch broad macro/market headlines from Google News RSS."""
    CONTEXT_QUERIES["__drivers__"] = _DRIVERS_QUERY
    results = _fetch_context_news("__drivers__")
    return jsonify(results)


@app.route("/api/news/search")
@login_required
def api_news_search():
    """Stateless Google News RSS search for an arbitrary query string."""
    q = freq.args.get("q", "").strip()[:200]
    if not q:
        return jsonify([])
    return jsonify(_fetch_news_for_query(q))


# ── Private Workspace API ─────────────────────────────────────────────────────

@app.route("/api/workspace/all", methods=["GET"])
@login_required
def api_workspace_all():
    """Return all saved workspace data for the current user (all firms)."""
    return jsonify(get_user_firms(session["user"]))


@app.route("/api/workspace/<firm_key>", methods=["GET"])
@login_required
def api_workspace_get(firm_key: str):
    """Return the current user's private workspace data for one firm."""
    return jsonify(get_firm_entry(session["user"], firm_key))


@app.route("/api/workspace/<firm_key>", methods=["POST"])
@login_required
def api_workspace_save(firm_key: str):
    """Save the current user's private workspace data for one firm."""
    body = freq.get_json(silent=True) or {}
    save_firm_entry(session["user"], firm_key, body)
    return jsonify({"ok": True})


@app.route("/api/account/password", methods=["POST"])
@login_required
def api_change_password():
    """Change the current user's password."""
    body        = freq.get_json(silent=True) or {}
    current_pw  = body.get("current_password", "")
    new_pw      = body.get("new_password", "")
    confirm_pw  = body.get("confirm_password", "")

    if not new_pw:
        return jsonify({"error": "New password cannot be empty."}), 400
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    if new_pw != confirm_pw:
        return jsonify({"error": "Passwords do not match."}), 400

    username  = session["user"]
    stored_pw = get_user_password(username)
    expected  = stored_pw if stored_pw is not None else config.USERS.get(username, "")
    if expected != current_pw:
        return jsonify({"error": "Current password is incorrect."}), 403

    save_user_password(username, new_pw)
    return jsonify({"ok": True})


@app.route("/api/favorites", methods=["GET"])
@login_required
def api_favorites_get():
    """Return the current user's list of favorited firm keys."""
    return jsonify(get_favorite_firms(session["user"]))


@app.route("/api/favorites", methods=["POST"])
@login_required
def api_favorites_save():
    """Save the current user's list of favorited firm keys."""
    body = freq.get_json(silent=True) or {}
    keys = body.get("keys", [])
    if isinstance(keys, list):
        save_favorite_firms(session["user"], keys)
    return jsonify({"ok": True})


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def home():
    return render_template(
        "index.html",
        refresh_seconds=REFRESH_SECONDS,
        username=session["user"],
    )

@app.route("/dashboard")
def dashboard_redirect():
    return redirect("/", code=301)


# ── Application startup ────────────────────────────────────────────────────────
# Runs when the module is imported — works under Gunicorn and direct invocation.

if not YFINANCE_AVAILABLE:
    print("[WARN] yfinance not installed — commodity prices unavailable.")

engine.start(REFRESH_SECONDS)


# ── Entry point (direct invocation only) ──────────────────────────────────────

if __name__ == "__main__":
    print("  MarketScope  ·  http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)

"""
local host  –  Database Layer
─────────────────────────────────────
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

import firebase_admin
from firebase_admin import credentials, firestore

from config import (
    FIREBASE_CRED_PATH, FIREBASE_DB_URL,
    FREE_DAILY_LIMIT, TOKEN_EXPIRY_DAYS,
    REFERRAL_BONUS_BYPASSES,
)

log = logging.getLogger(__name__)


# ─── Init ─────────────────────────────────────────────────────────────────────
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

init_firebase()
db = firestore.client()


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)

def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════════════════
# BOT SETTINGS  (maintenance mode, access mode)
# ══════════════════════════════════════════════════════════════════════════════

_SETTINGS_REF = lambda: db.collection("bot_settings").document("main")

def get_settings() -> dict:
    snap = _SETTINGS_REF().get()
    if snap.exists:
        return snap.to_dict()
    # Defaults
    return {
        "maintenance":   False,
        "access_mode":   "both",   # "pm" | "group" | "both"
    }

def update_setting(key: str, value):
    _SETTINGS_REF().set({key: value}, merge=True)

def is_maintenance() -> bool:
    return get_settings().get("maintenance", False)

def get_access_mode() -> str:
    return get_settings().get("access_mode", "both")

def set_maintenance(enabled: bool):
    update_setting("maintenance", enabled)

def set_access_mode(mode: str):
    """mode: 'pm' | 'group' | 'both'"""
    assert mode in ("pm", "group", "both"), "Invalid access mode"
    update_setting("access_mode", mode)


# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════

def get_user(uid: int) -> dict:
    snap = db.collection("users").document(str(uid)).get()
    return snap.to_dict() if snap.exists else {}


def upsert_user(uid: int, username: str = "", first_name: str = "",
                referrer_uid: Optional[int] = None) -> dict:
    """Get-or-create user document. Returns (user_dict, is_new)."""
    ref  = db.collection("users").document(str(uid))
    snap = ref.get()
    if snap.exists:
        return snap.to_dict(), False

    user = {
        "uid":              uid,
        "username":         username,
        "first_name":       first_name,
        "plan":             "free",
        "daily_used":       0,
        "daily_date":       _today_str(),
        "resets_today":     0,
        "reset_date":       _today_str(),
        "total_bypasses":   0,
        "bonus_bypasses":   0,       # referral bonus pool
        "is_banned":        False,
        "premium_until":    None,
        "premium_days":     None,
        "referrer_uid":     referrer_uid,
        "referral_count":   0,
        "referral_code":    _make_ref_code(uid),
        "bypass_history":   [],      # last 5 as [{url, result, ts}]
        "joined_at":        _now(),
    }
    ref.set(user)
    _increment_stat("total_users", 1)

    # Credit referrer
    if referrer_uid:
        _credit_referrer(referrer_uid)

    return user, True


def _make_ref_code(uid: int) -> str:
    return f"REF{uid}"


def _credit_referrer(referrer_uid: int):
    ref = db.collection("users").document(str(referrer_uid))
    ref.update({
        "referral_count":  firestore.Increment(1),
        "bonus_bypasses":  firestore.Increment(REFERRAL_BONUS_BYPASSES),
    })
    _increment_stat("total_referrals", 1)


def refresh_daily_if_needed(user: dict) -> dict:
    today   = _today_str()
    changed = False
    if user.get("daily_date") != today:
        user["daily_used"]   = 0
        user["daily_date"]   = today
        changed = True
    if user.get("reset_date") != today:
        user["resets_today"] = 0
        user["reset_date"]   = today
        changed = True
    if changed:
        db.collection("users").document(str(user["uid"])).update({
            "daily_used":   user["daily_used"],
            "daily_date":   user["daily_date"],
            "resets_today": user["resets_today"],
            "reset_date":   user["reset_date"],
        })
    return user


def check_plan_expiry(user: dict) -> dict:
    if user.get("plan") == "premium":
        until = user.get("premium_until")
        if until and isinstance(until, datetime) and _now() > until:
            db.collection("users").document(str(user["uid"])).update({
                "plan": "free", "premium_until": None, "premium_days": None,
            })
            user["plan"]          = "free"
            user["premium_until"] = None
    return user


def consume_usage(uid: int):
    db.collection("users").document(str(uid)).update({
        "daily_used":     firestore.Increment(1),
        "total_bypasses": firestore.Increment(1),
    })


def add_to_history(uid: int, original_url: str, result_url: str):
    """Keep last 5 bypass entries per user."""
    entry = {
        "url":    original_url,
        "result": result_url,
        "ts":     _now().strftime("%d %b %H:%M"),
    }
    ref  = db.collection("users").document(str(uid))
    snap = ref.get()
    if not snap.exists:
        return
    history = snap.to_dict().get("bypass_history", [])
    history.insert(0, entry)
    history = history[:5]          # keep only last 5
    ref.update({"bypass_history": history})


def get_history(uid: int) -> list:
    user = get_user(uid)
    return user.get("bypass_history", [])


def ban_user(uid: int, ban: bool = True):
    db.collection("users").document(str(uid)).update({"is_banned": ban})


def set_premium(uid: int, days: int = TOKEN_EXPIRY_DAYS):
    """
    days =  1   → 1-Day
    days =  30  → 1-Month
    days =  365 → 1-Year
    days = -1   → Lifetime (no expiry)
    """
    until = None if days == -1 else _now() + timedelta(days=days)
    db.collection("users").document(str(uid)).update({
        "plan":          "premium",
        "premium_until": until,
        "premium_days":  days,
    })


def list_users(limit: int = 50) -> list:
    return [d.to_dict() for d in db.collection("users").limit(limit).stream()]


def get_user_by_ref_code(code: str) -> Optional[dict]:
    docs = (db.collection("users")
              .where("referral_code", "==", code.upper())
              .limit(1)
              .stream())
    for d in docs:
        return d.to_dict()
    return None


# ══════════════════════════════════════════════════════════════════════════════
# TOKENS
# ══════════════════════════════════════════════════════════════════════════════

def generate_token(token_type: str, created_by: int,
                   quantity: int = 1, days: int = 30) -> list:
    """
    token_type : 'premium' | 'free_reset'
    days       : 1 / 7 / 30 / 90 / 180 / 365 / -1 (lifetime)
    """
    tokens = []
    batch  = db.batch()
    for _ in range(quantity):
        tok = str(uuid.uuid4()).replace("-", "")[:16].upper()
        ref = db.collection("tokens").document(tok)
        batch.set(ref, {
            "token":      tok,
            "type":       token_type,
            "days":       days,
            "used":       False,
            "created_by": created_by,
            "used_by":    None,
            "created_at": _now(),
            "used_at":    None,
        })
        tokens.append(tok)
    batch.commit()
    _increment_stat("tokens_generated", quantity)
    return tokens


def redeem_token(token: str, uid: int) -> dict:
    tok  = token.strip().upper()
    ref  = db.collection("tokens").document(tok)
    snap = ref.get()
    if not snap.exists:
        return {"ok": False, "reason": "Token not found."}
    data = snap.to_dict()
    if data["used"]:
        return {"ok": False, "reason": "This token has already been used."}

    ref.update({"used": True, "used_by": uid, "used_at": _now()})

    days = data.get("days", 30)
    if data["type"] == "premium":
        set_premium(uid, days=days)
    elif data["type"] == "free_reset":
        db.collection("users").document(str(uid)).update({
            "daily_used": 0, "daily_date": _today_str(),
        })

    return {"ok": True, "type": data["type"], "days": days}


def list_tokens(used: Optional[bool] = None, limit: int = 30) -> list:
    q = db.collection("tokens")
    if used is not None:
        q = q.where("used", "==", used)
    return [d.to_dict() for d in q.limit(limit).stream()]


# ══════════════════════════════════════════════════════════════════════════════
# FREE RESET
# ══════════════════════════════════════════════════════════════════════════════

def manual_reset(uid: int, max_resets: int) -> dict:
    ref  = db.collection("users").document(str(uid))
    snap = ref.get()
    if not snap.exists:
        return {"ok": False, "reason": "User not found."}
    user = snap.to_dict()
    user = refresh_daily_if_needed(user)
    if user.get("plan") == "premium":
        return {"ok": False, "reason": "Premium users have unlimited bypasses — no reset needed!"}
    if user.get("resets_today", 0) >= max_resets:
        return {"ok": False, "reason": f"You have used all {max_resets} reset(s) for today."}
    ref.update({"daily_used": 0, "resets_today": firestore.Increment(1)})
    return {"ok": True, "resets_left": max_resets - user.get("resets_today", 0) - 1}


# ══════════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════════

def _increment_stat(field: str, amount: int = 1):
    db.collection("stats").document("global").set(
        {field: firestore.Increment(amount)}, merge=True
    )


def log_bypass_stat(success: bool, site: str = "", cached: bool = False):
    updates = {"total_requests": firestore.Increment(1)}
    if success:
        updates["successful_bypasses"] = firestore.Increment(1)
    else:
        updates["failed_bypasses"] = firestore.Increment(1)
    if cached:
        updates["cache_hits"] = firestore.Increment(1)
    if site:
        updates[f"site_{site}"] = firestore.Increment(1)
    db.collection("stats").document("global").set(updates, merge=True)


def get_stats() -> dict:
    snap = db.collection("stats").document("global").get()
    return snap.to_dict() or {}

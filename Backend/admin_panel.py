"""
Admin Panel
───────────
All admin-only commands and callbacks.
• Duration picker for token generation  (1d / 1w / 1m / 3m / 6m / 1y / Lifetime)
• Duration picker for giving premium to a specific user
• Ban / Unban / Broadcast / Stats
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import ADMIN_IDS

from ui import (
    kb_admin, kb_user_actions, msg_admin_stats, msg_token_generated,
    kb_access_mode,
)
from database import (
    list_users, list_tokens, generate_token,
    ban_user, set_premium, get_stats, get_user,
    set_maintenance, is_maintenance, set_access_mode, get_access_mode,
)
from log_channel import log_ban, log_maintenance

log = logging.getLogger(__name__)

# ─── Shared duration map ─────────────────────────────────────────────────────
DURATION_LABELS = {
    1:   "1 Day",
    7:   "1 Week",
    30:  "1 Month",
    90:  "3 Months",
    180: "6 Months",
    365: "1 Year",
    -1:  "Lifetime ♾️",
}


def _duration_keyboard(cb_prefix: str) -> InlineKeyboardMarkup:
    """
    Builds a 4-row duration picker.
    Each button's callback_data = f"{cb_prefix}_{days}"
    e.g. cb_prefix="adm_dur"   → "adm_dur_30"
         cb_prefix="adm_give_999" → "adm_give_999_30"
    """
    p = cb_prefix
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Day",       callback_data=f"{p}_1"),
         InlineKeyboardButton("1 Week",      callback_data=f"{p}_7")],
        [InlineKeyboardButton("1 Month",     callback_data=f"{p}_30"),
         InlineKeyboardButton("3 Months",    callback_data=f"{p}_90")],
        [InlineKeyboardButton("6 Months",    callback_data=f"{p}_180"),
         InlineKeyboardButton("1 Year",      callback_data=f"{p}_365")],
        [InlineKeyboardButton("♾️ Lifetime",  callback_data=f"{p}_-1")],
        [InlineKeyboardButton("🔙 Cancel",   callback_data="adm_panel")],
    ])


# ─── Guard ───────────────────────────────────────────────────────────────────

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def guard(update: Update) -> bool:
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Admins only.")
        return False
    return True


# ─── /admin command ──────────────────────────────────────────────────────────

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await update.message.reply_text(
        "🛠️ <b>Admin Panel</b>\n\nChoose an action:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_admin(),
    )


# ─── Main callback dispatcher ────────────────────────────────────────────────

async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid  = query.from_user.id
    data = query.data

    if not is_admin(uid):
        await query.message.reply_text("⛔ Admins only.")
        return

    # ── Panel home ────────────────────────────────────────────────────────────
    if data == "adm_panel":
        await query.edit_message_text(
            "🛠️ <b>Admin Panel</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )

    # ── Users list ────────────────────────────────────────────────────────────
    elif data == "adm_users":
        users = list_users(limit=20)
        if not users:
            await query.edit_message_text("No users yet.", reply_markup=kb_admin())
            return
        lines = []
        for u in users:
            plan   = "⭐" if u.get("plan") == "premium" else "🆓"
            banned = " 🚫" if u.get("is_banned") else ""
            lines.append(
                f"{plan}{banned} <b>{u.get('first_name','?')}</b> "
                f"(<code>{u['uid']}</code>) — {u.get('total_bypasses', 0)} bypasses"
            )
        buttons = [
            [InlineKeyboardButton(
                f"{u.get('first_name','?')} ({u['uid']})",
                callback_data=f"adm_user_{u['uid']}",
            )]
            for u in users
        ]
        buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="adm_panel")])
        await query.edit_message_text(
            "👥 <b>Users</b> (latest 20)\n\n" + "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # ── Single user detail ────────────────────────────────────────────────────
    elif data.startswith("adm_user_"):
        target = int(data.replace("adm_user_", ""))
        user   = get_user(target)
        if not user:
            await query.edit_message_text("User not found.", reply_markup=kb_admin())
            return
        plan  = user.get("plan", "free")
        days  = user.get("premium_days", 30)
        until = user.get("premium_until")
        if plan == "premium":
            if days == -1 or until is None:
                expiry = "Never (Lifetime ♾️)"
            else:
                try:    expiry = until.strftime("%d %b %Y")
                except: expiry = "Unknown"
        else:
            expiry = "—"
        usage_str = "♾️ Unlimited" if plan == "premium" else "5"
        text = (
            f"👤 <b>User Detail</b>\n\n"
            f"🆔 ID: <code>{target}</code>\n"
            f"📛 Name: {user.get('first_name','?')}\n"
            f"🏷️ Username: @{user.get('username') or 'none'}\n"
            f"📋 Plan: {'⭐ Premium' if plan == 'premium' else '🆓 Free'}\n"
            f"⏳ Expires: {expiry}\n"
            f"📊 Used today: {user.get('daily_used', 0)} / {usage_str}\n"
            f"🔁 Total bypasses: {user.get('total_bypasses', 0)}\n"
            f"🚫 Banned: {'Yes' if user.get('is_banned') else 'No'}\n"
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb_user_actions(target, user.get("is_banned", False)),
        )

    # ── Ban / Unban ───────────────────────────────────────────────────────────
    elif data.startswith("adm_ban_") or data.startswith("adm_unban_"):
        action = "ban" if data.startswith("adm_ban_") else "unban"
        target = int(data.split("_")[-1])
        ban_user(target, action == "ban")
        await query.edit_message_text(
            f"{'🚫 Banned' if action == 'ban' else '✅ Unbanned'} "
            f"user <code>{target}</code>.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )
        try:
            msg = (
                "🚫 You have been <b>banned</b> from using this bot."
                if action == "ban"
                else "✅ You have been <b>unbanned</b>! Welcome back."
            )
            await ctx.bot.send_message(target, msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # ── Give Premium to user — Step 1: show duration picker ──────────────────
    elif data.startswith("adm_giveprem_"):
        target = int(data.replace("adm_giveprem_", ""))
        await query.edit_message_text(
            f"⏳ <b>Select premium duration for user <code>{target}</code>:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=_duration_keyboard(f"adm_give_{target}"),
        )

    # ── Give Premium to user — Step 2: apply chosen duration ─────────────────
    elif data.startswith("adm_give_"):
        # callback format:  adm_give_{uid}_{days}
        # split from right so uid can be any length
        rest   = data[len("adm_give_"):]          # e.g. "123456789_30"
        days   = int(rest.rsplit("_", 1)[-1])
        target = int(rest.rsplit("_", 1)[0])
        label  = DURATION_LABELS.get(days, f"{days} days")
        set_premium(target, days=days)
        await query.edit_message_text(
            f"⭐ User <code>{target}</code> upgraded to "
            f"<b>Premium — {label}</b>!",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )
        try:
            await ctx.bot.send_message(
                target,
                f"🎉 <b>Congratulations!</b>\n"
                f"An admin has upgraded you to <b>Premium</b>!\n\n"
                f"⚡ <b>Unlimited bypasses</b> activated!\n"
                f"⏳ Valid for: <b>{label}</b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    # ── Generate Premium Tokens — Step 1: show duration picker ───────────────
    elif data == "adm_gen_premium":
        ctx.user_data["pending_gen"] = "premium"
        await query.edit_message_text(
            "⏳ <b>Select token duration:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=_duration_keyboard("adm_dur"),
        )

    # ── Generate Premium Tokens — Step 2: duration chosen → ask quantity ─────
    elif data.startswith("adm_dur_"):
        days  = int(data.replace("adm_dur_", ""))
        label = DURATION_LABELS.get(days, f"{days} days")
        ctx.user_data["pending_gen_days"] = days
        await query.edit_message_text(
            f"🔢 Generating <b>Premium ({label})</b> tokens.\n"
            f"How many? Send a number (1–20):",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel")
            ]]),
        )
        ctx.user_data["awaiting_token_count"] = True

    # ── Generate Reset Tokens — go straight to quantity ───────────────────────
    elif data == "adm_gen_reset":
        ctx.user_data["pending_gen"]          = "free_reset"
        ctx.user_data["pending_gen_days"]     = 0
        ctx.user_data["awaiting_token_count"] = True
        await query.edit_message_text(
            "🔢 How many <b>Reset</b> tokens to generate?\n"
            "Send a number (1–20):",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel")
            ]]),
        )

    # ── Token list ────────────────────────────────────────────────────────────
    elif data == "adm_tokens":
        unused = list_tokens(used=False, limit=10)
        used_t = list_tokens(used=True,  limit=5)
        lines  = [f"🎫 <b>Active Tokens</b> ({len(unused)} shown)\n"]
        for t in unused:
            d   = t.get("days", 30)
            dur = DURATION_LABELS.get(d, f"{d}d") if d != 0 else "Reset"
            lines.append(f"  <code>{t['token']}</code> — {t['type']} · {dur}")
        lines.append(f"\n✅ <b>Recently Used</b> ({len(used_t)} shown)")
        for t in used_t:
            lines.append(
                f"  <s>{t['token']}</s> — used by <code>{t.get('used_by','?')}</code>"
            )
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )

    # ── Stats ─────────────────────────────────────────────────────────────────
    elif data == "adm_stats":
        stats = get_stats()
        users = list_users(limit=100000)
        await query.edit_message_text(
            msg_admin_stats(stats, len(users)),
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────
    elif data == "adm_broadcast":
        ctx.user_data["awaiting_broadcast"] = True
        await query.edit_message_text(
            "📢 <b>Broadcast</b>\n\n"
            "Send the message you want to blast to all users.\n"
            "HTML formatting is supported.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel")
            ]]),
        )

    # ── Maintenance toggle ────────────────────────────────────────────────────
    elif data == "adm_maintenance":
        current = is_maintenance()
        new_val = not current
        set_maintenance(new_val)
        await log_maintenance(uid, new_val)
        icon = "🔴 ON" if new_val else "🟢 OFF"
        await query.edit_message_text(
            f"🔧 <b>Maintenance Mode: {icon}</b>\n\n"
            f"{'All users will see the maintenance message.' if new_val else 'Bot is back online for all users.'}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )

    # ── Access mode ───────────────────────────────────────────────────────────
    elif data == "adm_access":
        current = get_access_mode()
        await query.edit_message_text(
            f"🔒 <b>Access Mode</b>\n\n"
            f"Current: <b>{current.upper()}</b>\n\n"
            "Choose where users can interact with the bot:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_access_mode(current),
        )

    elif data.startswith("adm_access_"):
        mode = data.replace("adm_access_", "")   # pm | group | both
        set_access_mode(mode)
        labels = {"pm": "💬 PM Only", "group": "👥 Group Only", "both": "🌐 Both"}
        await query.edit_message_text(
            f"✅ Access mode set to <b>{labels.get(mode, mode)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )

    # ── Cache purge ───────────────────────────────────────────────────────────
    elif data == "adm_cache_purge":
        await query.edit_message_text(
            "🗑️ Purging expired cache entries…",
            parse_mode=ParseMode.HTML,
        )
        from cache import purge_expired
        count = purge_expired()
        await query.edit_message_text(
            f"✅ <b>Cache Purged</b>\n\n"
            f"Removed <b>{count}</b> expired entries.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin(),
        )


# ─── Text input handler (token count + broadcast body) ───────────────────────

async def admin_message_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    text = update.message.text.strip()

    # Token quantity input
    if ctx.user_data.get("awaiting_token_count"):
        ctx.user_data.pop("awaiting_token_count")
        try:
            qty   = max(1, min(20, int(text)))
            ttype = ctx.user_data.pop("pending_gen",      "premium")
            days  = ctx.user_data.pop("pending_gen_days", 30)
            tokens = generate_token(ttype, uid, qty, days=days)
            label  = DURATION_LABELS.get(days, f"{days} days") if days != 0 else "Reset"
            await update.message.reply_text(
                msg_token_generated(tokens, ttype, label),
                parse_mode=ParseMode.HTML,
            )
        except ValueError:
            await update.message.reply_text("❌ Please send a valid number (1–20).")
        return

    # Broadcast body input
    if ctx.user_data.get("awaiting_broadcast"):
        ctx.user_data.pop("awaiting_broadcast")
        users = list_users(limit=100000)
        sent = failed = 0
        status = await update.message.reply_text(
            f"📢 Broadcasting to <b>{len(users)}</b> users…",
            parse_mode=ParseMode.HTML,
        )
        for u in users:
            try:
                await ctx.bot.send_message(u["uid"], text, parse_mode=ParseMode.HTML)
                sent += 1
            except Exception:
                failed += 1
        await status.edit_text(
            f"✅ <b>Broadcast complete!</b>\n\n"
            f"📨 Sent: <b>{sent}</b>  |  ❌ Failed: <b>{failed}</b>",
            parse_mode=ParseMode.HTML,
        )
        return

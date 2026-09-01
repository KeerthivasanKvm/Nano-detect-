"""
Main Bot  –  Entry Point
────────────────────────
Features wired here:
  ✅ Cache (hit before bypass, store after)
  ✅ Health check endpoint  /health  (GCP Cloud Run)
  ✅ Bypass history per user (last 5)
  ✅ Referral system  (/start REFxxxxx)
  ✅ Maintenance mode  (admin toggle)
  ✅ Access mode  (PM / Group / Both)
  ✅ Admin log channel
  ✅ Auto browser update on startup
  ✅ Webhook → Polling fallback
"""

import asyncio
import logging

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatAction

from config import (
    BOT_TOKEN, WEBHOOK_URL, PORT, SECRET_TOKEN,
    FREE_DAILY_LIMIT, FREE_RESET_PER_DAY, ADMIN_IDS,
    FORCE_JOIN_CHANNEL, LOG_CHANNEL_ID,
    REFERRAL_BONUS_BYPASSES,
)
from database import (
    upsert_user, get_user, refresh_daily_if_needed,
    check_plan_expiry, consume_usage, log_bypass_stat,
    manual_reset, redeem_token, add_to_history, get_history,
    get_user_by_ref_code, is_maintenance, get_access_mode,
)
from url_detector import detect_all
from bypass_engine import bypass
from cache import get_cached, set_cache
from browser_manager import close_browsers, browsers_ok, update_browsers
import log_channel as lc
from ui import (
    kb_start, kb_back, kb_result,
    msg_welcome, msg_how_to, msg_plan, msg_processing,
    msg_result, msg_error, msg_no_tokens, msg_banned,
    msg_redeem_prompt, msg_reset_success,
    msg_history, kb_history,
    msg_referral, kb_referral,
    msg_maintenance, msg_wrong_chat,
)
from admin_panel import (
    cmd_admin, admin_callback, admin_message_input, is_admin,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _daily_limit(user: dict):
    """Returns None for premium (unlimited), int for free."""
    return None if user.get("plan") == "premium" else FREE_DAILY_LIMIT


def _effective_limit(user: dict):
    """
    Effective remaining bypasses for free users:
    normal daily allowance + any referral bonus pool.
    """
    if user.get("plan") == "premium":
        return None
    used   = user.get("daily_used", 0)
    base   = FREE_DAILY_LIMIT - used
    bonus  = user.get("bonus_bypasses", 0)
    return base + bonus


async def _check_access(update: Update) -> bool:
    """
    Enforce group/pm/both mode.
    Returns True if the user is allowed to interact here.
    """
    mode    = get_access_mode()
    is_priv = update.effective_chat.type == "private"

    if mode == "pm"    and not is_priv:
        await update.effective_message.reply_text(
            msg_wrong_chat("pm"), parse_mode=ParseMode.HTML
        )
        return False
    if mode == "group" and is_priv:
        await update.effective_message.reply_text(
            msg_wrong_chat("group"), parse_mode=ParseMode.HTML
        )
        return False
    return True


async def _check_maintenance(update: Update) -> bool:
    """
    Block normal users when maintenance is ON.
    Admins always bypass maintenance.
    """
    if is_maintenance() and update.effective_user.id not in ADMIN_IDS:
        await update.effective_message.reply_text(
            msg_maintenance(), parse_mode=ParseMode.HTML
        )
        return False
    return True


async def _check_join(bot, uid: int) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(FORCE_JOIN_CHANNEL, uid)
        return member.status not in ("left", "kicked")
    except Exception:
        return True


async def _send_join_prompt(update: Update):
    channel = FORCE_JOIN_CHANNEL
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel",
                              url=f"https://t.me/{channel.lstrip('@')}")],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_joined")],
    ])
    text = (
        "📢 <b>Join Required</b>\n\n"
        "You must join our channel to use this bot.\n\n"
        "1️⃣ Click <b>Join Channel</b>\n"
        "2️⃣ Click <b>I've Joined</b> to verify"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb
        )


async def _get_or_create(update: Update, referrer_code: str = "") -> tuple:
    """Returns (user_dict, is_new)."""
    tg   = update.effective_user
    ref_uid = None
    if referrer_code:
        ref_user = get_user_by_ref_code(referrer_code)
        if ref_user and ref_user["uid"] != tg.id:
            ref_uid = ref_user["uid"]

    user, is_new = upsert_user(
        tg.id,
        username   = tg.username   or "",
        first_name = tg.first_name or "",
        referrer_uid = ref_uid,
    )
    if is_new:
        await lc.log_new_user(tg.id, tg.username or "", tg.first_name or "")
        if ref_uid:
            await lc.log_referral(ref_uid, tg.id, tg.first_name or "")
    return user, is_new


# ════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):      return
    if not await _check_maintenance(update): return

    # Check for referral code in deep-link  /start REF123456
    ref_code = ctx.args[0] if ctx.args else ""
    user, _  = await _get_or_create(update, referrer_code=ref_code)

    if user.get("is_banned"):
        await update.message.reply_text(msg_banned(), parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text(
        msg_welcome(update.effective_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_start(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    await update.message.reply_text(
        msg_how_to(), parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
    )


async def cmd_myplan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    uid     = update.effective_user.id
    user, _ = await _get_or_create(update)
    user    = refresh_daily_if_needed(user)
    user    = check_plan_expiry(user)
    await update.message.reply_text(
        msg_plan(user), parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
    )


async def cmd_redeem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    uid = update.effective_user.id
    if not ctx.args:
        await update.message.reply_text(
            msg_redeem_prompt(), parse_mode=ParseMode.HTML,
            reply_markup=kb_back("start")
        )
        return

    token  = ctx.args[0].strip()
    result = redeem_token(token, uid)

    if result["ok"]:
        ttype = result["type"]
        days  = result.get("days", 30)
        from database import DURATION_LABELS_MAP
        label = {1:"1 Day",7:"1 Week",30:"1 Month",90:"3 Months",
                 180:"6 Months",365:"1 Year",-1:"Lifetime ♾️"}.get(days, f"{days}d")
        await lc.log_token_redeemed(uid, update.effective_user.username or "",
                                    token, ttype, label)
        if ttype == "premium":
            dur_line = ("♾️ Your plan never expires!"
                        if days == -1 else f"⏳ Valid for: <b>{label}</b>")
            text = (
                "🎉 <b>Token Redeemed!</b>\n\n"
                "⭐ You are now a <b>Premium member</b>!\n"
                f"⚡ <b>Unlimited bypasses</b> activated!\n{dur_line}"
            )
        else:
            text = (
                "✅ <b>Reset Token Redeemed!</b>\n\n"
                "♻️ Your daily usage has been reset to 0.\n"
                "Go bypass some links! 🔗"
            )
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )
    else:
        await update.message.reply_text(
            f"❌ <b>Redeem Failed</b>\n\n{result['reason']}",
            parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    uid    = update.effective_user.id
    result = manual_reset(uid, FREE_RESET_PER_DAY)
    if result["ok"]:
        await update.message.reply_text(
            msg_reset_success(result["resets_left"]),
            parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )
    else:
        await update.message.reply_text(
            f"⚠️ <b>Reset Unavailable</b>\n\n{result['reason']}",
            parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    uid     = update.effective_user.id
    history = get_history(uid)
    await update.message.reply_text(
        msg_history(history), parse_mode=ParseMode.HTML,
        reply_markup=kb_history(history),
        disable_web_page_preview=True,
    )


async def cmd_referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _check_maintenance(update): return
    uid      = update.effective_user.id
    user, _  = await _get_or_create(update)
    bot_info = await ctx.bot.get_me()
    code     = user.get("referral_code", "")
    link     = f"https://t.me/{bot_info.username}?start={code}"
    await update.message.reply_text(
        msg_referral(user, bot_info.username, REFERRAL_BONUS_BYPASSES),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_referral(link),
        disable_web_page_preview=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# URL BYPASS HANDLER
# ════════════════════════════════════════════════════════════════════════════

async def handle_url_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text or ""

    # ── Admin text input passthrough ──────────────────────────────────────
    if is_admin(uid) and (
        ctx.user_data.get("awaiting_token_count") or
        ctx.user_data.get("awaiting_broadcast")
    ):
        await admin_message_input(update, ctx)
        return

    # ── Global guards ─────────────────────────────────────────────────────
    if not await _check_access(update):      return
    if not await _check_maintenance(update): return

    user, _ = await _get_or_create(update)
    if user.get("is_banned"):
        await update.message.reply_text(msg_banned(), parse_mode=ParseMode.HTML)
        return

    if not await _check_join(ctx.bot, uid):
        await _send_join_prompt(update)
        return

    user = refresh_daily_if_needed(user)
    user = check_plan_expiry(user)

    # ── Detect URLs ───────────────────────────────────────────────────────
    detected  = detect_all(text)
    supported = [d for d in detected if d.supported]

    if not supported:
        if detected:
            await update.message.reply_text(
                "⚠️ <b>Unsupported Link</b>\n\n"
                "This link type isn't supported yet.\n"
                "Supported: AdFly, LinkVertise, Ouo, Droplink, Try2Link, "
                "MediaFire, and 25+ more.",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── Usage limit check ────────────────────────────────────────────────
    remaining = _effective_limit(user)
    if remaining is not None and remaining <= 0:
        resets_left = max(0, FREE_RESET_PER_DAY - user.get("resets_today", 0))
        await update.message.reply_text(
            msg_no_tokens(user.get("daily_used", 0), FREE_DAILY_LIMIT, resets_left),
            parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )
        return

    await ctx.bot.send_chat_action(uid, ChatAction.TYPING)

    # ── Process each detected URL ─────────────────────────────────────────
    for det in supported:
        status_msg = await update.message.reply_text(
            msg_processing(det.label, det.emoji),
            parse_mode=ParseMode.HTML,
        )

        # ── Cache check ───────────────────────────────────────────────────
        cached_result = get_cached(det.raw)
        if cached_result:
            consume_usage(uid)
            add_to_history(uid, det.raw, cached_result)
            log_bypass_stat(True, det.category, cached=True)
            await lc.log_bypass(uid, update.effective_user.username or "",
                                 det.raw, cached_result, True, det.category, cached=True)
            await status_msg.edit_text(
                msg_result(det.raw, cached_result, det.emoji, det.label)
                + "\n\n⚡ <i>Served from cache</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb_result(cached_result),
            )
            continue

        # ── Live bypass ───────────────────────────────────────────────────
        try:
            result_url = await bypass(det.raw)
            consume_usage(uid)
            add_to_history(uid, det.raw, result_url)
            set_cache(det.raw, result_url)
            log_bypass_stat(True, det.category, cached=False)
            await lc.log_bypass(uid, update.effective_user.username or "",
                                 det.raw, result_url, True, det.category)
            await status_msg.edit_text(
                msg_result(det.raw, result_url, det.emoji, det.label),
                parse_mode=ParseMode.HTML,
                reply_markup=kb_result(result_url),
            )
        except Exception as e:
            log.error(f"Bypass error for {det.raw}: {e}")
            log_bypass_stat(False, det.category)
            await lc.log_bypass(uid, update.effective_user.username or "",
                                 det.raw, str(e), False, det.category)
            await lc.log_error(f"bypass [{det.category}]", str(e))
            await status_msg.edit_text(
                msg_error(str(e)[:200]),
                parse_mode=ParseMode.HTML,
                reply_markup=kb_back("start"),
            )


# ════════════════════════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ════════════════════════════════════════════════════════════════════════════

async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    # ── Force join recheck ───────────────────────────────────────────────
    if data == "check_joined":
        if await _check_join(ctx.bot, uid):
            await query.edit_message_text(
                "✅ <b>Verified!</b>\n\nWelcome! Send me any ad link to bypass it. 🚀",
                parse_mode=ParseMode.HTML, reply_markup=kb_start()
            )
        else:
            await query.answer("❌ You haven't joined yet!", show_alert=True)
        return

    # ── Admin callbacks ──────────────────────────────────────────────────
    if (data.startswith("adm_") or data.startswith("confirm_")
            or data.startswith("adm_give")):
        await admin_callback(update, ctx)
        return

    # ── Maintenance check for user callbacks ─────────────────────────────
    if is_maintenance() and uid not in ADMIN_IDS:
        await query.edit_message_text(
            msg_maintenance(), parse_mode=ParseMode.HTML
        )
        return

    # ── User callbacks ────────────────────────────────────────────────────
    if data == "start":
        user, _ = await _get_or_create(update)
        await query.edit_message_text(
            msg_welcome(query.from_user.first_name),
            parse_mode=ParseMode.HTML, reply_markup=kb_start()
        )

    elif data == "howto":
        await query.edit_message_text(
            msg_how_to(), parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )

    elif data == "myplan":
        user  = get_user(uid) or {}
        user  = refresh_daily_if_needed(user)
        user  = check_plan_expiry(user)
        await query.edit_message_text(
            msg_plan(user), parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )

    elif data == "redeem":
        await query.edit_message_text(
            msg_redeem_prompt(), parse_mode=ParseMode.HTML,
            reply_markup=kb_back("start")
        )

    elif data == "reset":
        result = manual_reset(uid, FREE_RESET_PER_DAY)
        if result["ok"]:
            await query.edit_message_text(
                msg_reset_success(result["resets_left"]),
                parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
            )
        else:
            await query.edit_message_text(
                f"⚠️ <b>Reset Unavailable</b>\n\n{result['reason']}",
                parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
            )

    elif data == "history":
        history = get_history(uid)
        await query.edit_message_text(
            msg_history(history), parse_mode=ParseMode.HTML,
            reply_markup=kb_history(history),
            disable_web_page_preview=True,
        )

    elif data == "referral":
        user     = get_user(uid) or {}
        bot_info = await ctx.bot.get_me()
        code     = user.get("referral_code", "")
        link     = f"https://t.me/{bot_info.username}?start={code}"
        await query.edit_message_text(
            msg_referral(user, bot_info.username, REFERRAL_BONUS_BYPASSES),
            parse_mode=ParseMode.HTML,
            reply_markup=kb_referral(link),
            disable_web_page_preview=True,
        )

    elif data == "stats":
        from database import get_stats
        stats = get_stats()
        site_lines = []
        for k, v in sorted(stats.items(),
                            key=lambda x: -x[1] if isinstance(x[1], int) else 0):
            if k.startswith("site_") and isinstance(v, int) and v > 0:
                site_lines.append(f"  • {k[5:].replace('_',' ').title()}: {v}")
        site_block = "\n".join(site_lines[:10]) or "  None yet"
        await query.edit_message_text(
            f"📊 <b>Global Stats</b>\n\n"
            f"📨 Total Requests: <b>{stats.get('total_requests', 0)}</b>\n"
            f"✅ Successful: <b>{stats.get('successful_bypasses', 0)}</b>\n"
            f"❌ Failed: <b>{stats.get('failed_bypasses', 0)}</b>\n"
            f"⚡ Cache Hits: <b>{stats.get('cache_hits', 0)}</b>\n\n"
            f"🔥 <b>Top Sites:</b>\n{site_block}",
            parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )

    elif data == "help":
        await query.edit_message_text(
            msg_how_to(), parse_mode=ParseMode.HTML, reply_markup=kb_back("start")
        )


# ════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINT  (GCP Cloud Run)
# ════════════════════════════════════════════════════════════════════════════

async def health_handler(request: web.Request) -> web.Response:
    """
    GET /health
    Returns 200 OK + JSON status.
    GCP Cloud Run uses this to decide if the container is healthy.
    """
    browser_status = await browsers_ok()
    maintenance    = is_maintenance()
    access_mode    = get_access_mode()

    payload = {
        "status":       "ok" if browser_status else "degraded",
        "browsers":     "ok" if browser_status else "error",
        "maintenance":  maintenance,
        "access_mode":  access_mode,
    }

    status_code = 200 if browser_status else 503
    return web.json_response(payload, status=status_code)


async def _start_health_server(port: int):
    """Run a tiny aiohttp server alongside the bot for /health."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/",       health_handler)    # Cloud Run root check
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"[Health] Listening on :{port}/health")


# ════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ════════════════════════════════════════════════════════════════════════════

def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("myplan",   cmd_myplan))
    app.add_handler(CommandHandler("redeem",   cmd_redeem))
    app.add_handler(CommandHandler("reset",    cmd_reset))
    app.add_handler(CommandHandler("history",  cmd_history))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("admin",    cmd_admin))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_router))

    # URL messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_url_message
    ))

    return app


# ════════════════════════════════════════════════════════════════════════════
# WEBHOOK  ↔  POLLING FALLBACK
# ════════════════════════════════════════════════════════════════════════════

async def _try_webhook(app: Application) -> bool:
    if not WEBHOOK_URL:
        log.info("[Webhook] WEBHOOK_URL not set — will use polling.")
        return False
    try:
        log.info(f"[Webhook] Registering → {WEBHOOK_URL}/webhook …")
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook",
            secret_token=SECRET_TOKEN,
            allowed_updates=["message", "callback_query"],
        )
        info = await app.bot.get_webhook_info()
        if info.last_error_message:
            log.warning(f"[Webhook] Telegram error: {info.last_error_message}")
            return False
        log.info(f"[Webhook] ✅ Active on :{PORT}")
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            secret_token=SECRET_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/webhook",
        )
        return True
    except Exception as e:
        log.error(f"[Webhook] ❌ Failed: {e}")
        try:
            await app.bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass
        return False


async def _run_polling(app: Application):
    log.info("[Polling] ✅ Starting long-polling …")
    await app.bot.delete_webhook(drop_pending_updates=False)
    await app.run_polling(allowed_updates=["message", "callback_query"])


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

async def main():
    # 1. Auto-update browsers (blocking, runs before event loop)
    await asyncio.get_event_loop().run_in_executor(None, update_browsers)

    # 2. Build bot app
    app = build_app()

    # 3. Wire log channel
    lc.set_bot(app.bot, LOG_CHANNEL_ID)

    # 4. Start health check HTTP server in background
    await _start_health_server(PORT if not WEBHOOK_URL else PORT + 1)

    # 5. Webhook → Polling fallback
    webhook_ok = await _try_webhook(app)
    if not webhook_ok:
        log.info("[Fallback] Switching to polling mode.")
        await _run_polling(app)

    await close_browsers()


if __name__ == "__main__":
    asyncio.run(main())

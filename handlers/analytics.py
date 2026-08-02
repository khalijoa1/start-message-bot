"""Operator-only analytics: how many people have started this bot, plus a
quick breakdown of recent growth and how much content (screens/buttons)
the operator has built so far.
"""
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func

from db import session
from handlers.common import admin_menu_kb, is_operator
from models import BotUser, Button, Screen

router = Router()


@router.callback_query(F.data == "admin:analytics")
async def show_analytics(query: types.CallbackQuery) -> None:
    if not is_operator(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return

    now = datetime.utcnow()
    async with session() as s:
        total_users = (await s.execute(select(func.count()).select_from(BotUser))).scalar() or 0
        new_today = (await s.execute(
            select(func.count()).select_from(BotUser).where(BotUser.first_seen >= now - timedelta(days=1))
        )).scalar() or 0
        new_week = (await s.execute(
            select(func.count()).select_from(BotUser).where(BotUser.first_seen >= now - timedelta(days=7))
        )).scalar() or 0
        screen_count = (await s.execute(select(func.count()).select_from(Screen))).scalar() or 0
        button_count = (await s.execute(select(func.count()).select_from(Button))).scalar() or 0

    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 ANALYTICS\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total users: {total_users}\n"
        f"🆕 New in last 24h: {new_today}\n"
        f"🆕 New in last 7 days: {new_week}\n\n"
        f"🖼 Screens: {screen_count}\n"
        f"🔘 Buttons: {button_count}"
    )
    try:
        await query.message.edit_text(text, reply_markup=admin_menu_kb())
    except TelegramBadRequest as e:
        # Tapping "Analytics" again when the counts haven't changed since
        # the last tap sends Telegram identical text+markup, which it
        # rejects with "message is not modified" instead of silently
        # no-op'ing - previously unhandled here, so it surfaced as a full
        # traceback and the callback just hung with a loading spinner on
        # the user's end. The counts genuinely not having changed isn't an
        # error worth logging; anything else from Telegram still is.
        if "message is not modified" not in str(e):
            raise
    await query.answer()

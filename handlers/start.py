"""Buyer/subscriber-facing: /start renders the root "start" screen; tapping
a button either opens a URL directly (Telegram handles that itself - no
callback involved) or jumps to another screen via a screen_<id> callback.

Navigation always sends a *new* message rather than editing the previous
one in place - screens can freely mix text-only and photo/video content,
and Telegram's editMessageMedia/editMessageText don't interchange cleanly
across that boundary, so a fresh message per screen is simpler and more
reliable than trying to edit around it.
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select

from db import session
from models import Button, ButtonAction, MediaType, Screen

router = Router()


async def _buttons_for(screen_id: int) -> list[Button]:
    async with session() as s:
        q = select(Button).where(Button.screen_id == screen_id).order_by(Button.position, Button.id)
        res = await s.execute(q)
        return list(res.scalars().all())


def _build_keyboard(buttons: list[Button]) -> types.InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = []
    for b in buttons:
        if b.action == ButtonAction.URL:
            rows.append([types.InlineKeyboardButton(text=b.label, url=b.url)])
        else:
            rows.append([types.InlineKeyboardButton(text=b.label, callback_data=f"screen_{b.target_screen_id}")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


async def send_screen(target, screen: Screen) -> None:
    """`target` is anything with .answer_photo/.answer_video/.answer -
    i.e. a Message (for /start) or a CallbackQuery's .message (for
    button-driven navigation)."""
    buttons = await _buttons_for(screen.id)
    kb = _build_keyboard(buttons)
    text = screen.text or "​"
    if screen.media_type == MediaType.PHOTO and screen.media_file_id:
        await target.answer_photo(screen.media_file_id, caption=text, reply_markup=kb, parse_mode="HTML")
    elif screen.media_type == MediaType.VIDEO and screen.media_file_id:
        await target.answer_video(screen.media_file_id, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    async with session() as s:
        q = select(Screen).where(Screen.key == "start")
        res = await s.execute(q)
        screen = res.scalars().first()
    if not screen:
        await message.answer("⚠️ Not set up yet - the operator needs to configure the start message.")
        return
    await send_screen(message, screen)


@router.callback_query(F.data.startswith("screen_"))
async def show_screen(query: types.CallbackQuery) -> None:
    screen_id = int(query.data.replace("screen_", ""))
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    if not screen:
        await query.answer("This button no longer leads anywhere - it may have been deleted.", show_alert=True)
        return
    await send_screen(query.message, screen)
    await query.answer()

"""Shared keyboards and small helpers used across handlers."""
from aiogram import types

from config import get_settings


def is_operator(user_id: int) -> bool:
    return user_id in get_settings().allowed_user_id_set


def admin_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ Edit Start Message", callback_data="admin:edit_start")],
        [types.InlineKeyboardButton(text="\U0001F4CB List Screens", callback_data="admin:list_screens")],
        [types.InlineKeyboardButton(text="➕ Add Screen", callback_data="admin:add_screen")],
        [types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="📊 Analytics", callback_data="admin:analytics")],
    ])


def cancel_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True,
    )

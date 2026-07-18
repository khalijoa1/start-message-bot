"""Catch-all fallback - registered LAST in bot.py so every other, more
specific handler gets first chance at an update. Purely diagnostic: logs
the user's FSM state alongside the raw update if any free-text step in
this bot ever goes silent (the failure mode discovered while building the
VVIP membership bot), so Railway logs show exactly what state the bot
thought the user was in instead of nothing at all.
"""
import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def fallback_message(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    logger.warning(
        "fallback_message: unmatched update from user_id=%s chat_id=%s fsm_state=%s text=%r",
        message.from_user.id, message.chat.id, current_state, message.text,
    )
    await message.answer(
        "\U0001F914 I didn't catch that. Use /start to see the menu, or /cancel if "
        "you were in the middle of something and want to restart it."
    )


@router.callback_query()
async def fallback_callback(query: types.CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    logger.warning(
        "fallback_callback: unmatched callback from user_id=%s fsm_state=%s data=%r",
        query.from_user.id, current_state, query.data,
    )
    await query.answer("That action isn't available anymore.", show_alert=True)

"""Operator-only: build and edit the bot's start message and any linked
screens entirely from Telegram - no redeploy needed to change wording,
swap the photo/video, or add/remove buttons.

Free text is unavoidable for message text, screen names, button labels,
and URLs - but every *choice* (button action type, which screen a button
should link to) is a tap, not typed text, since free-text FSM steps have
been the least reliable part of this family of bots in production (a
callback that sets FSM state and is immediately followed by a plain-text
message has occasionally gone unhandled - see the VVIP membership bot's
history). Callback-to-callback transitions, used throughout the
add-button flow below, were never observed to have that problem, so the
flow is designed to minimise how often a free-text step is the very next
update after a callback. See handlers/fallback.py for a diagnostic
catch-all in case a free-text step ever goes quiet anyway.
"""
import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from db import session
from handlers.common import admin_menu_kb, cancel_kb, is_operator
from models import Button, ButtonAction, MediaType, Screen

router = Router()
logger = logging.getLogger(__name__)


class EditTextState(StatesGroup):
    waiting_text = State()


class EditMediaState(StatesGroup):
    waiting_media = State()


class AddScreenState(StatesGroup):
    waiting_name = State()


class AddButtonState(StatesGroup):
    waiting_label = State()
    waiting_url = State()


def _op_guard(user_id: int) -> bool:
    return is_operator(user_id)


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled.", reply_markup=types.ReplyKeyboardRemove())


@router.message(Command("admin"))
async def admin_start(message: types.Message) -> None:
    if not _op_guard(message.from_user.id):
        return
    await message.answer("⚙️ ADMIN", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "menu:admin")
async def menu_admin(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    await query.message.edit_text("⚙️ ADMIN", reply_markup=admin_menu_kb())
    await query.answer()


# ---------------------------------------------------------------------------
# Screen list / edit menu
# ---------------------------------------------------------------------------

def _screen_edit_kb(screen_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="\U0001F4DD Edit Text", callback_data=f"scredit_text_{screen_id}")],
        [types.InlineKeyboardButton(text="\U0001F5BC Set Photo/Video", callback_data=f"scredit_media_{screen_id}")],
        [types.InlineKeyboardButton(text="\U0001F518 Manage Buttons", callback_data=f"scredit_buttons_{screen_id}")],
        [types.InlineKeyboardButton(text="\U0001F519 Back", callback_data="admin:list_screens")],
    ])


async def _show_screen_edit_menu(target, screen: Screen) -> None:
    """`target` is always something with .answer() - either a CallbackQuery's
    .message (the bot's own previous message) or a plain incoming user
    Message. Deliberately always sends a *new* message rather than editing
    in place: aiogram's Message.edit_text() exists on every Message
    instance, including a user's own incoming text message, so a
    hasattr()-based "edit if possible" check would end up trying to edit a
    message the bot doesn't own whenever this is called from a text-input
    flow (e.g. right after Add Screen or Edit Text) - which Telegram
    rejects. Always sending fresh avoids that class of bug entirely."""
    label = "\U0001F3E0 Start Message" if screen.key == "start" else screen.name
    media = {"none": "None", "photo": "Photo", "video": "Video"}[screen.media_type.value]
    async with session() as s:
        btn_count = len((await s.execute(select(Button).where(Button.screen_id == screen.id))).scalars().all())
    preview = (screen.text or "(empty)")[:300]
    text = f"✏️ {label}\n\nMedia: {media}\nButtons: {btn_count}\n\nText preview:\n{preview}"
    kb = _screen_edit_kb(screen.id)
    await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "admin:edit_start")
async def edit_start_shortcut(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    async with session() as s:
        screen = (await s.execute(select(Screen).where(Screen.key == "start"))).scalars().first()
    if not screen:
        await query.answer("Start screen missing - this shouldn't happen", show_alert=True)
        return
    await _show_screen_edit_menu(query.message, screen)
    await query.answer()


@router.callback_query(F.data == "admin:list_screens")
async def list_screens(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    async with session() as s:
        screens = (await s.execute(select(Screen))).scalars().all()
    rows = []
    for sc in screens:
        label = "\U0001F3E0 Start Message" if sc.key == "start" else sc.name
        rows.append([types.InlineKeyboardButton(text=label, callback_data=f"scredit_open_{sc.id}")])
    rows.append([types.InlineKeyboardButton(text="➕ Add Screen", callback_data="admin:add_screen")])
    rows.append([types.InlineKeyboardButton(text="\U0001F519 Back", callback_data="menu:admin")])
    await query.message.edit_text(
        "\U0001F4CB SCREENS\n\nTap one to edit:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await query.answer()


@router.callback_query(F.data.startswith("scredit_open_"))
async def open_screen_edit(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    screen_id = int(query.data.replace("scredit_open_", ""))
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    if not screen:
        await query.answer("Not found", show_alert=True)
        return
    await _show_screen_edit_menu(query.message, screen)
    await query.answer()


# ---------------------------------------------------------------------------
# Add screen
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin:add_screen")
async def add_screen_start(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    await state.clear()
    await query.message.answer(
        "➕ ADD SCREEN\n\nSend a short internal name for this screen (only you see this - "
        "it's just to help you tell screens apart, e.g. \"Pricing Info\" or \"FAQ\"):",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddScreenState.waiting_name)
    await query.answer()


@router.message(AddScreenState.waiting_name, F.text == "❌ Cancel")
async def cancel_add_screen(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled", reply_markup=types.ReplyKeyboardRemove())


@router.message(AddScreenState.waiting_name, F.text)
async def add_screen_name(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip()[:255]
    async with session() as s:
        screen = Screen(name=name, text=f"({name} - not yet written)")
        s.add(screen)
        await s.commit()
        screen_id = screen.id
    await state.clear()
    await message.answer(f"✅ Screen \"{name}\" created.", reply_markup=types.ReplyKeyboardRemove())
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    await _show_screen_edit_menu(message, screen)


# ---------------------------------------------------------------------------
# Edit text
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("scredit_text_"))
async def edit_text_start(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    screen_id = int(query.data.replace("scredit_text_", ""))
    await state.clear()
    await state.update_data(screen_id=screen_id)
    await query.message.answer(
        "\U0001F4DD Send the new message text.\n\nHTML formatting is supported: "
        "<b>bold</b>, <i>italic</i>, <a href=\"https://example.com\">link</a>.",
        reply_markup=cancel_kb()
    )
    await state.set_state(EditTextState.waiting_text)
    await query.answer()


@router.message(EditTextState.waiting_text, F.text == "❌ Cancel")
async def cancel_edit_text(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled", reply_markup=types.ReplyKeyboardRemove())


@router.message(EditTextState.waiting_text, F.text)
async def edit_text_save(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    screen_id = data["screen_id"]
    async with session() as s:
        screen = await s.get(Screen, screen_id)
        if not screen:
            await state.clear()
            await message.answer("❌ That screen no longer exists.", reply_markup=types.ReplyKeyboardRemove())
            return
        screen.text = message.text
        await s.commit()
    await state.clear()
    await message.answer("✅ Text updated.", reply_markup=types.ReplyKeyboardRemove())
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    await _show_screen_edit_menu(message, screen)


# ---------------------------------------------------------------------------
# Set media
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("scredit_media_"))
async def edit_media_start(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    screen_id = int(query.data.replace("scredit_media_", ""))
    await state.clear()
    await state.update_data(screen_id=screen_id)
    await query.message.answer(
        "\U0001F5BC Send a photo or video for this screen, or type \"remove\" to clear its current media:",
        reply_markup=cancel_kb()
    )
    await state.set_state(EditMediaState.waiting_media)
    await query.answer()


@router.message(EditMediaState.waiting_media, F.text == "❌ Cancel")
async def cancel_edit_media(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled", reply_markup=types.ReplyKeyboardRemove())


@router.message(EditMediaState.waiting_media, F.text.lower() == "remove")
async def remove_media(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    screen_id = data["screen_id"]
    async with session() as s:
        screen = await s.get(Screen, screen_id)
        if screen:
            screen.media_type = MediaType.NONE
            screen.media_file_id = None
            await s.commit()
    await state.clear()
    await message.answer("✅ Media removed.", reply_markup=types.ReplyKeyboardRemove())
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    if screen:
        await _show_screen_edit_menu(message, screen)


@router.message(EditMediaState.waiting_media, F.photo)
async def set_media_photo(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    screen_id = data["screen_id"]
    file_id = message.photo[-1].file_id
    async with session() as s:
        screen = await s.get(Screen, screen_id)
        if screen:
            screen.media_type = MediaType.PHOTO
            screen.media_file_id = file_id
            await s.commit()
    await state.clear()
    await message.answer("✅ Photo saved.", reply_markup=types.ReplyKeyboardRemove())
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    if screen:
        await _show_screen_edit_menu(message, screen)


@router.message(EditMediaState.waiting_media, F.video)
async def set_media_video(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    screen_id = data["screen_id"]
    file_id = message.video.file_id
    async with session() as s:
        screen = await s.get(Screen, screen_id)
        if screen:
            screen.media_type = MediaType.VIDEO
            screen.media_file_id = file_id
            await s.commit()
    await state.clear()
    await message.answer("✅ Video saved.", reply_markup=types.ReplyKeyboardRemove())
    async with session() as s:
        screen = await s.get(Screen, screen_id)
    if screen:
        await _show_screen_edit_menu(message, screen)


@router.message(EditMediaState.waiting_media)
async def set_media_invalid(message: types.Message) -> None:
    await message.answer("❌ Send a photo, a video, or type \"remove\".")


# ---------------------------------------------------------------------------
# Manage buttons
# ---------------------------------------------------------------------------

async def _buttons_kb(screen_id: int) -> types.InlineKeyboardMarkup:
    async with session() as s:
        q = select(Button).where(Button.screen_id == screen_id).order_by(Button.position, Button.id)
        buttons = (await s.execute(q)).scalars().all()
    rows = []
    for b in buttons:
        dest = b.url if b.action == ButtonAction.URL else f"screen #{b.target_screen_id}"
        rows.append([
            types.InlineKeyboardButton(text=f"{b.label} → {dest[:20]}", callback_data="noop"),
            types.InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delbtn_{b.id}_{screen_id}"),
        ])
    rows.append([types.InlineKeyboardButton(text="➕ Add Button", callback_data=f"addbtn_{screen_id}")])
    rows.append([types.InlineKeyboardButton(text="\U0001F519 Back", callback_data=f"scredit_open_{screen_id}")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("scredit_buttons_"))
async def manage_buttons(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    screen_id = int(query.data.replace("scredit_buttons_", ""))
    kb = await _buttons_kb(screen_id)
    await query.message.edit_text(
        "\U0001F518 BUTTONS\n\nTap \U0001F5D1 to remove a button, or add a new one:",
        reply_markup=kb
    )
    await query.answer()


@router.callback_query(F.data == "noop")
async def noop(query: types.CallbackQuery) -> None:
    await query.answer()


@router.callback_query(F.data.startswith("delbtn_"))
async def delete_button(query: types.CallbackQuery) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    _, btn_id_s, screen_id_s = query.data.split("_")
    btn_id, screen_id = int(btn_id_s), int(screen_id_s)
    async with session() as s:
        btn = await s.get(Button, btn_id)
        if btn:
            await s.delete(btn)
            await s.commit()
    kb = await _buttons_kb(screen_id)
    await query.message.edit_text(
        "\U0001F518 BUTTONS\n\nTap \U0001F5D1 to remove a button, or add a new one:",
        reply_markup=kb
    )
    await query.answer("Removed")


@router.callback_query(F.data.startswith("addbtn_"))
async def add_button_start(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    screen_id = int(query.data.replace("addbtn_", ""))
    await state.clear()
    await state.update_data(screen_id=screen_id)
    await query.message.answer(
        "➕ ADD BUTTON\n\nSend the button's label (short text shown on the button, e.g. \"Join Channel\"):",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddButtonState.waiting_label)
    await query.answer()


@router.message(AddButtonState.waiting_label, F.text == "❌ Cancel")
async def cancel_add_button(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled", reply_markup=types.ReplyKeyboardRemove())


@router.message(AddButtonState.waiting_label, F.text)
async def add_button_label(message: types.Message, state: FSMContext) -> None:
    label = message.text.strip()[:64]
    await state.update_data(label=label)
    await state.set_state(None)  # data (label/screen_id) stays; next step is callback-driven, not free-text
    await message.answer(f"Label: \"{label}\"", reply_markup=types.ReplyKeyboardRemove())
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="\U0001F517 Open a Link", callback_data="btnaction_url")],
        [types.InlineKeyboardButton(text="➡️ Show Another Screen", callback_data="btnaction_screen")],
    ])
    await message.answer("What should this button do when tapped?", reply_markup=kb)


@router.callback_query(F.data == "btnaction_url")
async def add_button_pick_url(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    await query.message.answer(
        "\U0001F517 Send the URL (must start with http:// or https://):",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddButtonState.waiting_url)
    await query.answer()


@router.message(AddButtonState.waiting_url, F.text == "❌ Cancel")
async def cancel_add_button_url(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Cancelled", reply_markup=types.ReplyKeyboardRemove())


@router.message(AddButtonState.waiting_url, F.text)
async def add_button_url(message: types.Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("❌ That doesn't look like a URL - it must start with http:// or https://. Try again:")
        return
    data = await state.get_data()
    screen_id, label = data["screen_id"], data["label"]
    async with session() as s:
        s.add(Button(screen_id=screen_id, label=label, action=ButtonAction.URL, url=url))
        await s.commit()
    await state.clear()
    await message.answer("✅ Button added.", reply_markup=types.ReplyKeyboardRemove())
    kb = await _buttons_kb(screen_id)
    await message.answer("\U0001F518 BUTTONS", reply_markup=kb)


@router.callback_query(F.data == "btnaction_screen")
async def add_button_pick_screen(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    async with session() as s:
        screens = (await s.execute(select(Screen))).scalars().all()
    rows = []
    for sc in screens:
        label = "\U0001F3E0 Start Message" if sc.key == "start" else sc.name
        rows.append([types.InlineKeyboardButton(text=label, callback_data=f"btntarget_{sc.id}")])
    rows.append([types.InlineKeyboardButton(text="➕ New Screen", callback_data="btntarget_new")])
    await query.message.answer(
        "➡️ Which screen should this button show?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await query.answer()


@router.callback_query(F.data.startswith("btntarget_"))
async def add_button_finish_screen(query: types.CallbackQuery, state: FSMContext) -> None:
    if not _op_guard(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    target = query.data.replace("btntarget_", "")
    data = await state.get_data()
    screen_id, label = data.get("screen_id"), data.get("label")
    if screen_id is None or label is None:
        await query.answer("Session expired - start over with Add Button.", show_alert=True)
        await state.clear()
        return

    if target == "new":
        new_name = f"{label} screen"
        async with session() as s:
            new_screen = Screen(name=new_name, text=f"({new_name} - not yet written)")
            s.add(new_screen)
            await s.flush()
            s.add(Button(screen_id=screen_id, label=label, action=ButtonAction.SCREEN, target_screen_id=new_screen.id))
            await s.commit()
        await query.message.answer(
            f"✅ Button added, linking to a new screen \"{new_name}\" - "
            f"edit it from \U0001F4CB List Screens."
        )
    else:
        target_id = int(target)
        async with session() as s:
            s.add(Button(screen_id=screen_id, label=label, action=ButtonAction.SCREEN, target_screen_id=target_id))
            await s.commit()
        await query.message.answer("✅ Button added.")

    await state.clear()
    kb = await _buttons_kb(screen_id)
    await query.message.answer("\U0001F518 BUTTONS", reply_markup=kb)
    await query.answer()

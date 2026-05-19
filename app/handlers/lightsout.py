import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.lightsout import game
from app.games.lightsout.keyboards import board_keyboard, size_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.menus import game_menu_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    format_leaderboard_text,
    get_game_leaderboard,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import update_user_settings, upsert_user


router = Router()


def lightsout_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_setting_key="size",
        chat_type=chat_type,
    )


async def start_lightsout_game(message: Message, user, lang: dict[str, str], size: int, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(size=size)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
        reply_markup=board_keyboard(session.id, session.state["cells"], size, True, lang),
    )


def _lto_menu_text(lang: dict, user_settings: dict | None) -> str:
    size = int((user_settings or {}).get("lightsout_size", 5))
    return f"{lang['icon-lightsout']} *{lang['game-lightsout']}*\n{lang['setting-size']}: {lang[str(size)]}✖️{lang[str(size)]}"


async def open_lightsout_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _lto_menu_text(lang, user.settings),
        reply_markup=lightsout_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("lightsout"))
async def cmd_lightsout_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_lightsout_menu(message, user, lang)


@router.callback_query(F.data == "game:lightsout")
async def open_lightsout_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, _lto_menu_text(lang, user.settings), reply_markup=lightsout_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("lightsout_size", 5))
    await start_lightsout_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("size", game.code))
async def menu_size(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("lightsout_size", 5))
    cur = f"{lang[str(size)]}✖️{lang[str(size)]}"
    text = f"{lang['chus-size']}\n\n{lang['setting-size']}: {cur}"
    await safe_edit(callback.message, text, reply_markup=size_keyboard(lang, "game:lightsout"))
    await callback.answer()


@router.callback_query(GameCallbackFilter("top", game.code))
async def menu_top(callback: CallbackQuery, user, lang) -> None:
    entries, viewer_entry = await get_game_leaderboard(game.code, viewer_user_id=user.id)
    title = f"*{lang['game-lightsout']}*"
    text = format_leaderboard_text(entries, title, lang, viewer_entry)
    await safe_edit(callback.message, text, reply_markup=lightsout_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "lto:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("lto:size:"))
async def callback_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"lightsout_size": size, "current_game": game.code})
    updated = dict(user.settings or {})
    updated["lightsout_size"] = size
    await safe_edit(
        callback.message,
        _lto_menu_text(lang, updated),
        reply_markup=lightsout_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )


@router.callback_query(F.data.startswith("lto:press:"))
async def callback_press(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    _, _, session_id_text, idx_text = callback.data.split(":")
    session_id = int(session_id_text)
    idx = int(idx_text)
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    result = game.press(state, idx)
    state = result["game_state"]
    size = state["size"]
    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win", variant_key=str(state["size"]), best_score=state.get("taps", 0))
        await callback.message.edit_text(
            lang["game-win"],
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_lightsout_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
        reply_markup=board_keyboard(session.id, state["cells"], size, True, lang),
    )


@router.callback_query(F.data.startswith("lto:give_up:"))
async def callback_give_up(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    session_id = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    await finish_session(session.id, state, winner_user_id=None)
    await record_game_result(user.id, game.code, "loss", variant_key=str(state["size"]))
    await callback.message.edit_text(
        lang["game-lose"],
    )
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_lightsout_menu(callback.message, user, lang)


@router.callback_query(F.data.startswith("lto:solve:"))
async def callback_solve(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    session_id = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    size = state["size"]
    menu_msg_id = state.get("menu_message_id")
    solution = game.solve(state)

    for idx in solution:
        await asyncio.sleep(1)
        result = game.press(state, idx)
        state = result["game_state"]
        await callback.message.edit_text(
            f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
            reply_markup=board_keyboard(session.id, state["cells"], size, False),  # animation step
        )

    await callback.message.edit_text(lang["game-win"])
    await finish_session(session.id, state, winner_user_id=None)
    # No stat recorded — solver was used
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_lightsout_menu(callback.message, user, lang)

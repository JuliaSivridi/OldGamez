from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.memory import game
from app.games.memory.game import GRID_DIMS
from app.games.memory.keyboards import board_keyboard, size_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.menus import game_menu_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    format_game_stats_text,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import update_user_settings, upsert_user

router = Router()


def memory_menu_keyboard(lang: dict, chat_type=None):
    return game_menu_keyboard(lang, game_code=game.code, extra_setting_key="size", chat_type=chat_type)


def _mem_menu_text(lang: dict, user_settings: dict | None) -> str:
    size = int((user_settings or {}).get("memory_size", 4))
    rows, cols = GRID_DIMS[size]
    return f"{lang['game-mem']}\n{lang['setting-size']}: {lang[str(rows)]}✖️{lang[str(cols)]}"


def render_text(lang: dict, state: dict, final: bool = False) -> str:
    rows, cols = state["rows"], state["cols"]
    total_pairs = len(state["cards"]) // 2
    header = f"{lang['game-mem']} · {rows}×{cols}"
    if final:
        return f"{header}\n\n{lang['game-win']}\n{lang['mem-win']}{state['moves']}{lang['mem-win2']}"
    return f"{header}\n\n{lang['mem-moves']}{state['moves']}  {lang['mem-found']}{state['found']}/{total_pairs}"


async def start_memory_game(message: Message, user, lang: dict, size: int, menu_message_id: int | None = None) -> None:
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
        render_text(lang, state),
        reply_markup=board_keyboard(session.id, state, True),
    )


async def open_memory_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _mem_menu_text(lang, user.settings),
        reply_markup=memory_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("memory"))
async def cmd_memory_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_memory_menu(message, user, lang)


@router.callback_query(F.data == "game:mem")
async def open_memory_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(
        callback.message,
        _mem_menu_text(lang, user.settings),
        reply_markup=memory_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("memory_size", 4))
    await start_memory_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("size", game.code))
async def menu_size(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("memory_size", 4))
    rows, cols = GRID_DIMS[size]
    cur = f"{lang[str(rows)]}✖️{lang[str(cols)]}"
    text = f"{lang['chus-size']}\n\n{lang['setting-size']}: {cur}"
    await safe_edit(callback.message, text, reply_markup=size_keyboard(lang, "game:mem"))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins"])
    await safe_edit(callback.message, text, reply_markup=memory_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-mem"], reply_markup=memory_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data.startswith("mem:size:"))
async def callback_set_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"memory_size": size, "current_game": game.code})
    updated = dict(user.settings or {})
    updated["memory_size"] = size
    await safe_edit(
        callback.message,
        _mem_menu_text(lang, updated),
        reply_markup=memory_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )


@router.callback_query(F.data == "mem:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("mem:flip:"))
async def callback_flip(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    parts = callback.data.split(":")
    session_id = int(parts[2])
    idx = int(parts[3])

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)

    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        await callback.answer()
        return

    state = dict(session.state)
    flipped: list[int] = list(state.get("flipped", []))

    if state.get("revealing") or state["matched"][idx]:
        await callback.answer()
        return

    if len(flipped) == 1 and flipped[0] == idx:
        await callback.answer()
        return

    if len(flipped) == 0:
        # First card
        state["flipped"] = [idx]
        await update_session_state(session.id, state, user.id)
        await callback.message.edit_text(render_text(lang, state), reply_markup=board_keyboard(session.id, state, True))
        await callback.answer()
        return

    # Second card
    first = flipped[0]
    state["flipped"] = [first, idx]
    state["moves"] += 1

    if state["cards"][first] == state["cards"][idx]:
        # Match
        state["matched"][first] = True
        state["matched"][idx] = True
        state["found"] += 1
        state["flipped"] = []
        total_pairs = len(state["cards"]) // 2

        if state["found"] == total_pairs:
            state["status"] = "won"
            await finish_session(session.id, state, winner_user_id=user.id)
            await record_game_result(user.id, game.code, "win")
            await callback.message.edit_text(
                render_text(lang, state, final=True),
                reply_markup=board_keyboard(session.id, state, False),
            )
            menu_msg_id = state.get("menu_message_id")
            if menu_msg_id:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
                except Exception:
                    pass
            await open_memory_menu(callback.message, user, lang)
        else:
            await update_session_state(session.id, state, user.id)
            await callback.message.edit_text(render_text(lang, state), reply_markup=board_keyboard(session.id, state, True))
    else:
        # Mismatch — show both for 1.5s then flip back
        state["revealing"] = True
        await update_session_state(session.id, state, user.id)
        await callback.message.edit_text(render_text(lang, state), reply_markup=board_keyboard(session.id, state, False))
        await callback.answer()

        await asyncio.sleep(1.5)

        state["flipped"] = []
        state["revealing"] = False
        await update_session_state(session.id, state, user.id)
        try:
            await callback.message.edit_text(render_text(lang, state), reply_markup=board_keyboard(session.id, state, True))
        except Exception:
            pass
        return

    await callback.answer()

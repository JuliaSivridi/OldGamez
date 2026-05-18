from __future__ import annotations

import asyncio
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionMode, SessionStatus
from app.games.memory import game
from app.games.memory.game import GRID_DIMS
from app.games.memory.keyboards import board_keyboard, size_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard
from app.keyboards.menus import game_menu_keyboard
from app.services.duels import (
    broadcast_private_duel_update,
    build_duel_invite_text,
    delete_guest_join_msg,
    get_duel_message_map,
    set_duel_message_ref,
)
from app.services.sessions import (
    activate_private_duel_session,
    create_private_duel_invite,
    create_solo_session,
    finish_session,
    format_game_stats_text,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import get_user_by_id, update_user_settings, upsert_user

router = Router()


def memory_menu_keyboard(lang: dict, chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_setting_key="size",
        extra_duel_key="duel",
        chat_type=chat_type,
    )


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


def render_duel_text(lang: dict, state: dict, viewer_id: int, final: bool = False) -> str:
    rows, cols = state["rows"], state["cols"]
    total_pairs = len(state["cards"]) // 2
    header = f"{lang['game-mem']} · {rows}×{cols}"

    is_p1 = viewer_id == state["p1_id"]
    my_found = state["p1_found"] if is_p1 else state["p2_found"]
    opp_found = state["p2_found"] if is_p1 else state["p1_found"]
    score = f"{lang['mem-you']}{my_found}  {lang['mem-opp']}{opp_found}/{total_pairs}"

    if final:
        p1f, p2f = state["p1_found"], state["p2_found"]
        winner_id = state["p1_id"] if p1f > p2f else (state["p2_id"] if p2f > p1f else None)
        if winner_id is None:
            result = lang["game-draw"]
        elif winner_id == viewer_id:
            result = f"{lang['game-win']}\n{lang['mem-win']}{state['moves']}{lang['mem-win2']}"
        else:
            result = lang["game-lose"]
        return f"{header}\n\n{score}\n\n{result}"

    turn_line = lang["mem-your-turn"] if state.get("current_turn_user_id") == viewer_id else lang["mem-opp-turn"]
    return f"{header}\n\n{score}\n{turn_line}"


async def _sync_mem_duel(bot, session_id: int, state: dict, final: bool = False) -> None:
    p1_id = state["p1_id"]
    p2_id = state["p2_id"]
    message_map = get_duel_message_map(state)
    current_turn_id = state.get("current_turn_user_id")

    async def renderer(user_id: int):
        u = await get_user_by_id(user_id)
        lang = get_language_pack(u.language_code if u else "en")
        is_active = not final and user_id == current_turn_id
        return render_duel_text(lang, state, user_id, final=final), board_keyboard(session_id, state, is_active)

    await broadcast_private_duel_update(bot, [p1_id, p2_id], message_map, renderer)


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


async def join_memory_duel(message: Message, user, lang: dict, session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"])
        return

    size = state.get("size", 4)
    duel_state = game.new_duel_state(session.created_by_user_id, user.id, size)
    duel_state["message_ids"] = get_duel_message_map(state)

    first_player = random.choice([session.created_by_user_id, user.id])
    duel_state["current_turn_user_id"] = first_player

    activated = await activate_private_duel_session(
        session.id, user.id, duel_state, current_turn_user_id=first_player,
    )
    if activated is None:
        await message.answer(lang["duel-missing"])
        return

    await update_user_settings(user.id, {"current_game": game.code})
    join_ok_msg = await message.answer(
        lang["duel-join-ok"],
        reply_markup=memory_menu_keyboard(lang, chat_type=message.chat.type),
    )
    duel_state["guest_join_msg"] = {"chat_id": join_ok_msg.chat.id, "message_id": join_ok_msg.message_id}

    guest_board_msg = await message.answer(
        render_duel_text(lang, duel_state, user.id),
        reply_markup=board_keyboard(activated.id, duel_state, first_player == user.id),
    )
    set_duel_message_ref(duel_state, user.id, guest_board_msg)

    updated = await update_session_state(activated.id, duel_state, first_player)
    if updated:
        await _sync_mem_duel(message.bot, activated.id, dict(updated.state))


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


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("memory_size", 4))
    state: dict = {"status": "pending", "size": size, "message_ids": {}}
    session = await create_private_duel_invite(user.id, callback.message.chat.id, game.code, state)
    invite_msg = await callback.message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or ""),
    )
    set_duel_message_ref(state, user.id, invite_msg)
    await update_session_state(session.id, state, None)
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

    if session is None or session.status != SessionStatus.active:
        await callback.answer()
        return

    if session.mode == SessionMode.duel_private:
        await _flip_duel(callback, session, user, lang, idx)
    else:
        await _flip_solo(callback, session, user, lang, idx)


async def _flip_solo(callback: CallbackQuery, session, user, lang: dict, idx: int) -> None:
    if session.created_by_user_id != user.id:
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
        state["flipped"] = [idx]
        await update_session_state(session.id, state, user.id)
        await callback.message.edit_text(render_text(lang, state), reply_markup=board_keyboard(session.id, state, True))
        await callback.answer()
        return

    first = flipped[0]
    state["flipped"] = [first, idx]
    state["moves"] += 1

    if state["cards"][first] == state["cards"][idx]:
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


async def _flip_duel(callback: CallbackQuery, session, user, lang: dict, idx: int) -> None:
    state = dict(session.state)

    if user.id not in {state.get("p1_id"), state.get("p2_id")}:
        await callback.answer()
        return
    if state.get("current_turn_user_id") != user.id:
        await callback.answer()
        return

    flipped: list[int] = list(state.get("flipped", []))

    if state.get("revealing") or state["matched"][idx]:
        await callback.answer()
        return
    if len(flipped) == 1 and flipped[0] == idx:
        await callback.answer()
        return

    await callback.answer()

    if len(flipped) == 0:
        state["flipped"] = [idx]
        await update_session_state(session.id, state, user.id)
        await _sync_mem_duel(callback.bot, session.id, state)
        return

    first = flipped[0]
    state["flipped"] = [first, idx]
    state["moves"] += 1

    if state["cards"][first] == state["cards"][idx]:
        state["matched"][first] = True
        state["matched"][idx] = True
        state["found"] += 1
        state["flipped"] = []

        is_p1 = user.id == state["p1_id"]
        if is_p1:
            state["p1_found"] += 1
        else:
            state["p2_found"] += 1

        total_pairs = len(state["cards"]) // 2
        if state["found"] == total_pairs:
            p1f, p2f = state["p1_found"], state["p2_found"]
            winner_id = state["p1_id"] if p1f > p2f else (state["p2_id"] if p2f > p1f else None)
            p1_result = "win" if p1f > p2f else ("loss" if p1f < p2f else "draw")
            p2_result = "win" if p2f > p1f else ("loss" if p2f < p1f else "draw")
            state["status"] = "finished"
            await finish_session(session.id, state, winner_user_id=winner_id)
            await record_game_result(state["p1_id"], game.code, p1_result)
            await record_game_result(state["p2_id"], game.code, p2_result)
            await _sync_mem_duel(callback.bot, session.id, state, final=True)
            await delete_guest_join_msg(callback.bot, state)
            await open_memory_menu(callback.message, user, lang)
            other_id = state["p2_id"] if is_p1 else state["p1_id"]
            other_user = await get_user_by_id(other_id)
            if other_user:
                other_lang = get_language_pack(other_user.language_code)
                msg_meta = get_duel_message_map(state).get(str(other_id))
                if msg_meta:
                    try:
                        await callback.bot.send_message(
                            chat_id=msg_meta["chat_id"],
                            text=_mem_menu_text(other_lang, other_user.settings),
                            reply_markup=memory_menu_keyboard(other_lang),
                        )
                    except Exception:
                        pass
        else:
            await update_session_state(session.id, state, user.id)
            await _sync_mem_duel(callback.bot, session.id, state)
    else:
        state["revealing"] = True
        await update_session_state(session.id, state, user.id)
        await _sync_mem_duel(callback.bot, session.id, state)

        await asyncio.sleep(1.5)

        state["flipped"] = []
        state["revealing"] = False
        next_player = state["p2_id"] if user.id == state["p1_id"] else state["p1_id"]
        state["current_turn_user_id"] = next_player
        await update_session_state(session.id, state, next_player)
        try:
            await _sync_mem_duel(callback.bot, session.id, state)
        except Exception:
            pass

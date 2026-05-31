from __future__ import annotations

import asyncio
import random

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionMode, SessionStatus
from app.games.sheepwolves.game import SheepWolvesGame
from app.games.sheepwolves.keyboards import board_keyboard
from app.handlers.common import get_game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard, group_duel_keyboard
from app.keyboards.menus import main_menu_keyboard
from app.services.duels import (
    broadcast_private_duel_update,
    build_duel_invite_text,
    delete_guest_join_msg,
    get_duel_message_map,
    set_duel_message_ref,
)
from app.services.levels import level_icon
from app.services.sessions import (
    activate_group_match_session,
    activate_private_duel_session,
    create_group_match_session,
    create_private_duel_invite,
    create_solo_session,
    finish_session,
    get_game_streak_line,
    get_session_by_id,
    record_game_result,
    update_session_state,
    xp_gain_from_state,
    xp_gain_line,
    xp_group_line,
)
from app.services.users import format_player_name, get_user_by_id, update_user_settings, upsert_user

router = Router()
game = SheepWolvesGame()

COMP_MOVE_DELAY = 0.5


# ── Menu text ─────────────────────────────────────────────────────────────────

def _sw_menu_text(lang: dict) -> str:
    return f"{lang['icon-sw']} *{lang['game-sw']}*"


async def open_sw_menu(message: Message, user, lang: dict) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    streak = await get_game_streak_line(user.id, game.code, lang)
    await message.answer(
        _sw_menu_text(lang) + streak,
        reply_markup=get_game_keyboard(game.code, lang, chat_type=message.chat.type),
    )


# ── Status text ───────────────────────────────────────────────────────────────

def render_status(state: dict, lang: dict, *, is_duel: bool = False) -> str:
    player_side = state["player_side"]
    side_line = lang["sw-you-sheep"] if player_side == "sheep" else lang["sw-you-wolves"]

    if state["status"] == "finished":
        winner = state["winner"]
        player_won = (winner == player_side)
        result_line = lang["game-win"] if player_won else lang["game-lose"]
        return f"{lang['icon-sw']} {lang['game-sw']}\n{side_line}\n\n{result_line}"

    turn = state["turn"]
    piece = lang["sw-sheep"] if turn == "sheep" else lang["sw-wolf"]
    if turn == player_side:
        turn_line = lang["turn-user"]
    elif is_duel:
        turn_line = lang["turn-friend"]
    else:
        turn_line = lang["turn-comp"]
    return f"{lang['icon-sw']} {lang['game-sw']}\n{side_line}\n\n{piece} {turn_line}"


def render_sw_group_text(state: dict, lang: dict, player_names: dict) -> str:
    sheep_uid = state.get("sheep_user_id")
    wolves_uid = state.get("wolves_user_id")
    sheep_name = player_names.get(sheep_uid, "?")
    wolves_name = player_names.get(wolves_uid, "?")
    piece_s = lang["sw-sheep"]
    piece_w = lang["sw-wolf"]
    header = (
        f"{lang['icon-sw']} {lang['game-sw']}\n"
        f"{piece_s} {sheep_name} — {piece_w} {wolves_name}"
    )

    if state.get("status") == "finished":
        winner = state.get("winner")
        winner_uid = sheep_uid if winner == "sheep" else wolves_uid
        winner_name = player_names.get(winner_uid, "?")
        return f"{header}\n\n{lang['group-winner']} {winner_name}"

    turn = state.get("turn")
    piece = piece_s if turn == "sheep" else piece_w
    curr_uid = state.get("current_turn_user_id")
    curr_name = player_names.get(curr_uid, "?")
    return f"{header}\n\n{lang['group-turn']} {piece} {curr_name}"


# ── Keyboard helpers ──────────────────────────────────────────────────────────

def _active_keyboard(session_id: int, state: dict, lang: dict) -> object:
    """Return the right interactive keyboard for the current state."""
    sheep = state["sheep"]
    wolves = state["wolves"]
    turn = state["turn"]
    player_side = state["player_side"]
    selected_wolf = state.get("selected_wolf")

    if turn == "sheep" and player_side == "sheep":
        targets = game.sheep_moves(sheep, wolves)
        return board_keyboard(session_id, sheep, wolves, lang, sheep_targets=targets)

    if turn == "wolves" and player_side == "wolves":
        all_moves = game.all_wolf_moves(wolves, sheep)
        selectables = {wi for wi, _ in all_moves}
        if selected_wolf is not None and selected_wolf in selectables:
            wolf_targets = game.wolf_moves_for(selected_wolf, wolves, sheep)
            return board_keyboard(
                session_id, sheep, wolves, lang,
                wolf_targets=wolf_targets,
                selected_wolf=selected_wolf,
                wolf_selectables=selectables,
            )
        return board_keyboard(session_id, sheep, wolves, lang, wolf_selectables=selectables)

    return board_keyboard(session_id, sheep, wolves, lang)


def _inactive_keyboard(session_id: int, state: dict, lang: dict) -> object:
    return board_keyboard(session_id, state["sheep"], state["wolves"], lang)


def _group_keyboard(session_id: int, state: dict, lang: dict) -> object:
    """Active keyboard for group mode — shows moves for whoever's turn it is."""
    view_state = {**state, "player_side": state["turn"]}
    return _active_keyboard(session_id, view_state, lang)


# ── Duel helpers ──────────────────────────────────────────────────────────────

def _duel_player_ids(state: dict) -> list[int | None]:
    return [state.get("sheep_user_id"), state.get("wolves_user_id")]


async def _get_player_names(state: dict) -> dict:
    names: dict[int, str] = {}
    for uid in _duel_player_ids(state):
        if uid is not None:
            u = await get_user_by_id(uid)
            names[uid] = format_player_name(u) if u else str(uid)
    return names


async def _render_sw_for_user(session, user_id: int) -> tuple[str, object]:
    """Render board + text for a specific player (used for private duel sync)."""
    u = await get_user_by_id(user_id)
    lang = get_language_pack(u.language_code if u else "en")
    state = dict(session.state or {})
    sheep_uid = state.get("sheep_user_id")
    viewer_side = "sheep" if user_id == sheep_uid else "wolves"
    view_state = {**state, "player_side": viewer_side}

    text = render_status(view_state, lang, is_duel=True)
    if session.status == SessionStatus.finished and state.get("xp_gains"):
        gain = xp_gain_from_state(state, user_id)
        text += xp_gain_line(gain, lang)

    if session.status == SessionStatus.finished:
        markup = _inactive_keyboard(session.id, state, lang)
    elif session.current_turn_user_id == user_id:
        markup = _active_keyboard(session.id, view_state, lang)
    else:
        markup = _inactive_keyboard(session.id, state, lang)

    return text, markup


async def _sync_sw_duel_messages(bot, session) -> None:
    state = dict(session.state or {})
    await broadcast_private_duel_update(
        bot,
        _duel_player_ids(state),
        get_duel_message_map(state),
        lambda uid: _render_sw_for_user(session, uid),
    )


async def _send_sw_menu_to_other_player(
    bot,
    state: dict,
    excluded_uid: int,
    current_chat_id: int,
    current_chat_type,
) -> None:
    message_map = get_duel_message_map(state)
    for uid in _duel_player_ids(state):
        if uid is None or uid == excluded_uid:
            continue
        meta = message_map.get(str(uid))
        if not meta:
            continue
        u = await get_user_by_id(uid)
        if u is None:
            continue
        lang = get_language_pack(u.language_code)
        chat_type = current_chat_type if meta["chat_id"] == current_chat_id else ChatType.PRIVATE
        try:
            await bot.send_message(
                chat_id=meta["chat_id"],
                text=_sw_menu_text(lang),
                reply_markup=get_game_keyboard(game.code, lang, chat_type=chat_type),
            )
        except TelegramBadRequest:
            pass


# ── Finish helpers ────────────────────────────────────────────────────────────

async def _finish_game(
    message: Message,
    session_id: int,
    state: dict,
    lang: dict,
    user,
    winner: str,
) -> None:
    """Finish solo session."""
    state["winner"] = winner
    state["status"] = "finished"

    player_side = state["player_side"]
    result = "win" if winner == player_side else "loss"

    await finish_session(session_id, state, winner_user_id=user.id if result == "win" else None)
    xp = await record_game_result(user.id, game.code, result)

    await message.edit_text(
        render_status(state, lang) + xp_gain_line(xp, lang),
        reply_markup=_inactive_keyboard(session_id, state, lang),
    )

    menu_msg_id = state.get("menu_message_id")
    if menu_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, menu_msg_id)
        except Exception:
            pass

    await open_sw_menu(message, user, lang)


async def _finish_duel_game(
    callback: CallbackQuery,
    session,
    state: dict,
    lang: dict,
    user,
    winner: str,
) -> None:
    """Finish a private duel: record XP, sync both boards, send menus."""
    state["winner"] = winner
    state["status"] = "finished"
    state["current_turn_user_id"] = None

    sheep_uid = state["sheep_user_id"]
    wolves_uid = state["wolves_user_id"]
    winner_uid = sheep_uid if winner == "sheep" else wolves_uid
    loser_uid = wolves_uid if winner == "sheep" else sheep_uid

    await finish_session(session.id, state, winner_user_id=winner_uid)
    xp_winner = await record_game_result(winner_uid, game.code, "win")
    xp_loser = await record_game_result(loser_uid, game.code, "loss")
    state["xp_gains"] = {
        str(winner_uid): {
            "xp": xp_winner.xp,
            "leveled_up": xp_winner.level_up.number if xp_winner.level_up else None,
        },
        str(loser_uid): {
            "xp": xp_loser.xp,
            "leveled_up": xp_loser.level_up.number if xp_loser.level_up else None,
        },
    }
    await update_session_state(session.id, state, None)
    refreshed = await get_session_by_id(session.id)
    if refreshed:
        await _sync_sw_duel_messages(callback.bot, refreshed)

    await delete_guest_join_msg(callback.bot, state)
    menu_msg_id = state.get("menu_message_id")
    menu_chat = state.get("menu_chat_id")
    if menu_msg_id and menu_chat:
        try:
            await callback.bot.delete_message(menu_chat, menu_msg_id)
        except Exception:
            pass

    await open_sw_menu(callback.message, user, lang)
    await _send_sw_menu_to_other_player(
        callback.bot, state,
        excluded_uid=user.id,
        current_chat_id=callback.message.chat.id,
        current_chat_type=callback.message.chat.type,
    )


async def _finish_group_game(
    callback: CallbackQuery,
    session,
    state: dict,
    lang: dict,
    user,
    winner: str,
    player_names: dict,
    group_lang: dict,
) -> None:
    """Finish a group match: record XP, update shared message, send menu."""
    state["winner"] = winner
    state["status"] = "finished"
    state["current_turn_user_id"] = None

    sheep_uid = state["sheep_user_id"]
    wolves_uid = state["wolves_user_id"]
    winner_uid = sheep_uid if winner == "sheep" else wolves_uid
    loser_uid = wolves_uid if winner == "sheep" else sheep_uid

    await finish_session(session.id, state, winner_user_id=winner_uid)
    xp_winner = await record_game_result(winner_uid, game.code, "win")
    xp_loser = await record_game_result(loser_uid, game.code, "loss")

    winner_obj = await get_user_by_id(winner_uid)
    w_icon = level_icon(winner_obj.xp or 0, group_lang) if winner_obj else ""

    await callback.message.edit_text(
        render_sw_group_text(state, group_lang, player_names)
        + f" {w_icon}".rstrip()
        + xp_group_line(
            [
                (player_names.get(winner_uid, "?"), xp_winner),
                (player_names.get(loser_uid, "?"), xp_loser),
            ],
            group_lang,
        ),
        reply_markup=_inactive_keyboard(session.id, state, group_lang),
    )

    menu_msg_id = state.get("menu_message_id")
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass

    await open_sw_menu(callback.message, user, lang)


# ── Computer move helpers ─────────────────────────────────────────────────────

async def _do_comp_wolves_move(
    message: Message,
    session,
    state: dict,
    lang: dict,
    user,
) -> None:
    wi, dest = game.best_wolf_move(state["sheep"], state["wolves"])
    state["wolves"][wi] = dest
    state["selected_wolf"] = None

    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(message, session.id, state, lang, user, winner)
        return

    state["turn"] = "sheep"
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await message.edit_text(
        render_status(state, lang),
        reply_markup=_active_keyboard(session.id, state, lang),
    )


async def _do_comp_sheep_move(
    message: Message,
    session,
    state: dict,
    lang: dict,
    user,
) -> None:
    dest = game.best_sheep_move(state["sheep"], state["wolves"])
    state["sheep"] = dest

    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(message, session.id, state, lang, user, winner)
        return

    state["turn"] = "wolves"
    state["selected_wolf"] = None
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await message.edit_text(
        render_status(state, lang),
        reply_markup=_active_keyboard(session.id, state, lang),
    )


# ── Start solo game ───────────────────────────────────────────────────────────

async def start_sheep_wolves_game(
    message: Message, user, lang: dict, menu_message_id: int | None = None
) -> None:
    player_side = random.choice(["sheep", "wolves"])
    state = game.new_game_state(player_side)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id

    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    state = dict(session.state)

    if player_side == "wolves":
        msg = await message.answer(
            render_status(state, lang),
            reply_markup=_inactive_keyboard(session.id, state, lang),
        )
        await asyncio.sleep(COMP_MOVE_DELAY)
        await _do_comp_sheep_move(msg, session, state, lang, user)
    else:
        await message.answer(
            render_status(state, lang),
            reply_markup=_active_keyboard(session.id, state, lang),
        )


# ── Start duel ────────────────────────────────────────────────────────────────

async def start_sw_duel(
    message: Message,
    user,
    lang: dict,
    menu_message_id: int | None = None,
    menu_chat_id: int | None = None,
) -> None:
    state: dict = {"status": "pending", "message_ids": {}}
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    if menu_chat_id:
        state["menu_chat_id"] = menu_chat_id
    session = await create_private_duel_invite(user.id, message.chat.id, game.code, state)
    invite_msg = await message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or "", game_name=lang["game-sw"]),
    )
    set_duel_message_ref(state, user.id, invite_msg)
    await update_session_state(session.id, state, None)


async def join_sw_duel(message: Message, user, lang: dict, session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"])
        return

    duel_state = game.new_duel_state(session.created_by_user_id, user.id)
    duel_state["message_ids"] = get_duel_message_map(state)
    if state.get("menu_message_id"):
        duel_state["menu_message_id"] = state["menu_message_id"]
    if state.get("menu_chat_id"):
        duel_state["menu_chat_id"] = state["menu_chat_id"]

    activated = await activate_private_duel_session(
        session.id, user.id, duel_state,
        current_turn_user_id=duel_state["current_turn_user_id"],
    )
    if activated is None:
        await message.answer(lang["duel-missing"])
        return

    await update_user_settings(user.id, {"current_game": game.code})
    join_ok_msg = await message.answer(
        lang["duel-join-ok"],
        reply_markup=get_game_keyboard(game.code, lang, chat_type=message.chat.type),
    )
    duel_state["guest_join_msg"] = {
        "chat_id": join_ok_msg.chat.id,
        "message_id": join_ok_msg.message_id,
    }

    sheep_uid = duel_state["sheep_user_id"]
    viewer_side = "sheep" if user.id == sheep_uid else "wolves"
    view_state = {**duel_state, "player_side": viewer_side}
    is_my_turn = duel_state["current_turn_user_id"] == user.id

    guest_msg = await message.answer(
        render_status(view_state, lang, is_duel=True),
        reply_markup=(
            _active_keyboard(activated.id, view_state, lang)
            if is_my_turn
            else _inactive_keyboard(activated.id, duel_state, lang)
        ),
    )
    set_duel_message_ref(duel_state, user.id, guest_msg)
    updated = await update_session_state(activated.id, duel_state, duel_state["current_turn_user_id"])
    if updated:
        await _sync_sw_duel_messages(message.bot, updated)


# ── Start group ───────────────────────────────────────────────────────────────

async def start_sw_group(
    message: Message, user, lang: dict, menu_message_id: int | None = None
) -> None:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.answer(
            lang["group-only"],
            reply_markup=get_game_keyboard(game.code, lang, chat_type=message.chat.type),
        )
        return

    state: dict = {"status": "pending"}
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_group_match_session(user.id, message.chat.id, game.code, state)
    await message.answer(
        lang["group-wait"],
        reply_markup=group_duel_keyboard(lang, f"sw:group_join:{session.id}"),
    )
    await update_session_state(session.id, state, None)


# ── Menu callbacks ────────────────────────────────────────────────────────────

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_sheep_wolves_game(
        callback.message, user, lang,
        menu_message_id=callback.message.message_id,
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel(callback: CallbackQuery, user, lang) -> None:
    await start_sw_duel(
        callback.message, user, lang,
        menu_message_id=callback.message.message_id,
        menu_chat_id=callback.message.chat.id,
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("group", game.code))
async def menu_new_group(callback: CallbackQuery, user, lang) -> None:
    await start_sw_group(
        callback.message, user, lang,
        menu_message_id=callback.message.message_id,
    )
    await callback.answer()


# ── Group join ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sw:group_join:"))
async def callback_sw_group_join(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    session_id = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)

    if session is None or session.mode != SessionMode.group_match:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return
    if session.created_by_user_id == user.id:
        await callback.answer(lang["duel-self"], show_alert=True)
        return
    if session.status != SessionStatus.pending:
        await callback.answer(lang["duel-full"], show_alert=True)
        return

    player_ids = {player.user_id for player in session.players}
    if user.id in player_ids:
        await callback.answer(lang["group-already-joined"], show_alert=True)
        return
    if len(player_ids) >= 2:
        await callback.answer(lang["duel-full"], show_alert=True)
        return

    original_state = dict(session.state or {})
    duel_state = game.new_duel_state(session.created_by_user_id, user.id)
    if original_state.get("menu_message_id"):
        duel_state["menu_message_id"] = original_state["menu_message_id"]

    session = await activate_group_match_session(
        session.id, user.id, duel_state, duel_state["current_turn_user_id"]
    )
    if session is None:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return

    player_names = await _get_player_names(duel_state)
    initiator = await get_user_by_id(session.created_by_user_id)
    group_lang = get_language_pack(initiator.language_code if initiator else user.language_code)

    await callback.message.edit_text(
        render_sw_group_text(duel_state, group_lang, player_names),
        reply_markup=_group_keyboard(session.id, duel_state, group_lang),
    )
    await callback.answer(lang["duel-join-ok"])


# ── Noop ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "sw:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Sheep move ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sw:sm:"))
async def callback_sheep_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    session_id, r, c = int(parts[2]), int(parts[3]), int(parts[4])
    dest = [r, c]

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return

    state = dict(session.state or {})

    # ── Group mode ───────────────────────────────────────────────────────────
    if session.mode == SessionMode.group_match:
        if session.current_turn_user_id != user.id:
            return
        if state.get("sheep_user_id") != user.id or state.get("turn") != "sheep":
            return
        if dest not in game.sheep_moves(state["sheep"], state["wolves"]):
            return

        state["sheep"] = dest
        winner = game.check_winner(state["sheep"], state["wolves"])
        player_names = await _get_player_names(state)
        initiator = await get_user_by_id(session.created_by_user_id)
        group_lang = get_language_pack(initiator.language_code if initiator else user.language_code)

        if winner:
            await _finish_group_game(callback, session, state, lang, user, winner, player_names, group_lang)
            return

        wolves_uid = state["wolves_user_id"]
        state["turn"] = "wolves"
        state["selected_wolf"] = None
        state["current_turn_user_id"] = wolves_uid
        await update_session_state(session_id, state, wolves_uid)
        await callback.message.edit_text(
            render_sw_group_text(state, group_lang, player_names),
            reply_markup=_group_keyboard(session_id, state, group_lang),
        )
        return

    # ── Private duel ─────────────────────────────────────────────────────────
    if session.mode == SessionMode.duel_private:
        if session.current_turn_user_id != user.id:
            return
        if state.get("sheep_user_id") != user.id or state.get("turn") != "sheep":
            return
        if dest not in game.sheep_moves(state["sheep"], state["wolves"]):
            return

        state["sheep"] = dest
        winner = game.check_winner(state["sheep"], state["wolves"])
        if winner:
            await _finish_duel_game(callback, session, state, lang, user, winner)
            return

        wolves_uid = state["wolves_user_id"]
        state["turn"] = "wolves"
        state["selected_wolf"] = None
        state["current_turn_user_id"] = wolves_uid
        updated = await update_session_state(session_id, state, wolves_uid)
        if updated:
            await _sync_sw_duel_messages(callback.bot, updated)
        return

    # ── Solo mode ─────────────────────────────────────────────────────────────
    if session.created_by_user_id != user.id:
        return
    if state.get("turn") != "sheep" or state.get("player_side") != "sheep":
        return
    if dest not in game.sheep_moves(state["sheep"], state["wolves"]):
        return

    state["sheep"] = dest
    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(callback.message, session_id, state, lang, user, winner)
        return

    state["turn"] = "wolves"
    await update_session_state(session_id, state, current_turn_user_id=None)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_inactive_keyboard(session_id, state, lang),
    )
    await asyncio.sleep(COMP_MOVE_DELAY)
    await _do_comp_wolves_move(callback.message, session, state, lang, user)


# ── Wolf select (step 1) ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sw:ws:"))
async def callback_wolf_select(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    session_id, wolf_idx = int(parts[2]), int(parts[3])

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return

    state = dict(session.state or {})
    if not game.wolf_moves_for(wolf_idx, state["wolves"], state["sheep"]):
        return  # wolf has no valid moves

    # ── Group mode ───────────────────────────────────────────────────────────
    if session.mode == SessionMode.group_match:
        if session.current_turn_user_id != user.id:
            return
        if state.get("wolves_user_id") != user.id or state.get("turn") != "wolves":
            return

        state["selected_wolf"] = wolf_idx
        await update_session_state(session_id, state, user.id)
        player_names = await _get_player_names(state)
        initiator = await get_user_by_id(session.created_by_user_id)
        group_lang = get_language_pack(initiator.language_code if initiator else user.language_code)
        await callback.message.edit_text(
            render_sw_group_text(state, group_lang, player_names),
            reply_markup=_group_keyboard(session_id, state, group_lang),
        )
        return

    # ── Private duel ─────────────────────────────────────────────────────────
    if session.mode == SessionMode.duel_private:
        if session.current_turn_user_id != user.id:
            return
        if state.get("wolves_user_id") != user.id or state.get("turn") != "wolves":
            return

        state["selected_wolf"] = wolf_idx
        updated = await update_session_state(session_id, state, user.id)
        if updated:
            await _sync_sw_duel_messages(callback.bot, updated)
        return

    # ── Solo mode ─────────────────────────────────────────────────────────────
    if session.created_by_user_id != user.id:
        return
    if state.get("turn") != "wolves" or state.get("player_side") != "wolves":
        return

    state["selected_wolf"] = wolf_idx
    await update_session_state(session_id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_active_keyboard(session_id, state, lang),
    )


# ── Wolf move (step 2) ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sw:wm:"))
async def callback_wolf_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    session_id, wolf_idx, r, c = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
    dest = [r, c]

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return

    state = dict(session.state or {})
    if dest not in game.wolf_moves_for(wolf_idx, state["wolves"], state["sheep"]):
        return

    # ── Group mode ───────────────────────────────────────────────────────────
    if session.mode == SessionMode.group_match:
        if session.current_turn_user_id != user.id:
            return
        if state.get("wolves_user_id") != user.id or state.get("turn") != "wolves":
            return

        state["wolves"][wolf_idx] = dest
        state["selected_wolf"] = None
        winner = game.check_winner(state["sheep"], state["wolves"])
        player_names = await _get_player_names(state)
        initiator = await get_user_by_id(session.created_by_user_id)
        group_lang = get_language_pack(initiator.language_code if initiator else user.language_code)

        if winner:
            await _finish_group_game(callback, session, state, lang, user, winner, player_names, group_lang)
            return

        sheep_uid = state["sheep_user_id"]
        state["turn"] = "sheep"
        state["current_turn_user_id"] = sheep_uid
        await update_session_state(session_id, state, sheep_uid)
        await callback.message.edit_text(
            render_sw_group_text(state, group_lang, player_names),
            reply_markup=_group_keyboard(session_id, state, group_lang),
        )
        return

    # ── Private duel ─────────────────────────────────────────────────────────
    if session.mode == SessionMode.duel_private:
        if session.current_turn_user_id != user.id:
            return
        if state.get("wolves_user_id") != user.id or state.get("turn") != "wolves":
            return

        state["wolves"][wolf_idx] = dest
        state["selected_wolf"] = None
        winner = game.check_winner(state["sheep"], state["wolves"])
        if winner:
            await _finish_duel_game(callback, session, state, lang, user, winner)
            return

        sheep_uid = state["sheep_user_id"]
        state["turn"] = "sheep"
        state["current_turn_user_id"] = sheep_uid
        updated = await update_session_state(session_id, state, sheep_uid)
        if updated:
            await _sync_sw_duel_messages(callback.bot, updated)
        return

    # ── Solo mode ─────────────────────────────────────────────────────────────
    if session.created_by_user_id != user.id:
        return
    if state.get("turn") != "wolves" or state.get("player_side") != "wolves":
        return

    state["wolves"][wolf_idx] = dest
    state["selected_wolf"] = None
    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(callback.message, session_id, state, lang, user, winner)
        return

    state["turn"] = "sheep"
    await update_session_state(session_id, state, current_turn_user_id=None)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_inactive_keyboard(session_id, state, lang),
    )
    await asyncio.sleep(COMP_MOVE_DELAY)
    await _do_comp_sheep_move(callback.message, session, state, lang, user)

from __future__ import annotations

import asyncio
import random

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.sheepwolves.game import SheepWolvesGame
from app.games.sheepwolves.keyboards import board_keyboard
from app.handlers.common import get_game_keyboard, open_game_menu
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.services.sessions import (
    create_solo_session,
    finish_session,
    get_game_streak_line,
    get_session_by_id,
    record_game_result,
    update_session_state,
    xp_gain_line,
)
from app.services.users import update_user_settings, upsert_user

router = Router()
game = SheepWolvesGame()

COMP_MOVE_DELAY = 0.5


# ── Menu text ─────────────────────────────────────────────────────────────────

def _sw_menu_text(lang: dict) -> str:
    return f"{lang['icon-sw']} *{lang['game-sw']}*"


async def open_sw_menu(message: Message, user, lang: dict) -> None:
    await open_game_menu(message, user, lang, game.code)


# ── Status text ───────────────────────────────────────────────────────────────

def render_status(state: dict, lang: dict) -> str:
    player_side = state["player_side"]
    side_line = lang["sw-you-sheep"] if player_side == "sheep" else lang["sw-you-wolves"]

    if state["status"] == "finished":
        winner = state["winner"]
        player_won = (winner == player_side)
        result_line = lang["game-win"] if player_won else lang["game-lose"]
        return f"{lang['icon-sw']} {lang['game-sw']}\n{side_line}\n\n{result_line}"

    turn = state["turn"]
    piece = "🐑" if turn == "sheep" else "🐺"
    turn_line = lang["turn-user"] if turn == player_side else lang["turn-comp"]
    return f"{lang['icon-sw']} {lang['game-sw']}\n{side_line}\n\n{piece} {turn_line}"


# ── Keyboard builder (context-aware) ─────────────────────────────────────────

def _active_keyboard(session_id: int, state: dict) -> object:
    """Return the right keyboard for the current interactive state."""
    sheep = state["sheep"]
    wolves = state["wolves"]
    turn = state["turn"]
    player_side = state["player_side"]
    selected_wolf = state.get("selected_wolf")

    if turn == "sheep" and player_side == "sheep":
        targets = game.sheep_moves(sheep, wolves)
        return board_keyboard(session_id, sheep, wolves, sheep_targets=targets)

    if turn == "wolves" and player_side == "wolves":
        all_moves = game.all_wolf_moves(wolves, sheep)
        selectables = {wi for wi, _ in all_moves}
        if selected_wolf is not None and selected_wolf in selectables:
            wolf_targets = game.wolf_moves_for(selected_wolf, wolves, sheep)
            return board_keyboard(
                session_id, sheep, wolves,
                wolf_targets=wolf_targets,
                selected_wolf=selected_wolf,
                wolf_selectables=selectables,
            )
        return board_keyboard(session_id, sheep, wolves, wolf_selectables=selectables)

    # Computer's turn — inactive board
    return board_keyboard(session_id, sheep, wolves)


def _inactive_keyboard(session_id: int, state: dict) -> object:
    return board_keyboard(session_id, state["sheep"], state["wolves"])


# ── Computer move helpers ─────────────────────────────────────────────────────

async def _finish_game(
    message: Message,
    session_id: int,
    state: dict,
    lang: dict,
    user,
    winner: str,
) -> None:
    """Finalize session, record XP, show result, open menu."""
    state["winner"] = winner
    state["status"] = "finished"

    player_side = state["player_side"]
    result = "win" if winner == player_side else "loss"

    await finish_session(
        session_id, state,
        winner_user_id=user.id if result == "win" else None,
    )
    xp = await record_game_result(user.id, game.code, result)

    await message.edit_text(
        render_status(state, lang) + xp_gain_line(xp, lang),
        reply_markup=_inactive_keyboard(session_id, state),
    )

    menu_msg_id = state.get("menu_message_id")
    if menu_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, menu_msg_id)
        except Exception:
            pass

    await open_sw_menu(message, user, lang)


async def _do_comp_wolves_move(
    message: Message,
    session,
    state: dict,
    lang: dict,
    user,
) -> None:
    """Computer plays as wolves: pick best move, apply, update state."""
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
        reply_markup=_active_keyboard(session.id, state),
    )


async def _do_comp_sheep_move(
    message: Message,
    session,
    state: dict,
    lang: dict,
    user,
) -> None:
    """Computer plays as sheep: pick best move, apply, update state."""
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
        reply_markup=_active_keyboard(session.id, state),
    )


# ── Start game ────────────────────────────────────────────────────────────────

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
        # Show initial board (computer as sheep moves first)
        msg = await message.answer(
            render_status(state, lang),
            reply_markup=_inactive_keyboard(session.id, state),
        )
        await asyncio.sleep(COMP_MOVE_DELAY)
        await _do_comp_sheep_move(msg, session, state, lang, user)
    else:
        # Player is sheep — show valid sheep moves immediately
        await message.answer(
            render_status(state, lang),
            reply_markup=_active_keyboard(session.id, state),
        )


# ── Menu handler ──────────────────────────────────────────────────────────────

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_sheep_wolves_game(
        callback.message, user, lang,
        menu_message_id=callback.message.message_id,
    )
    await callback.answer()


# ── Noop ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "sw:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Sheep move (player = sheep) ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("sw:sm:"))
async def callback_sheep_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    # sw:sm:{session_id}:{r}:{c}
    session_id, r, c = int(parts[2]), int(parts[3]), int(parts[4])
    dest = [r, c]

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return
    if session.created_by_user_id != user.id:
        return

    state = dict(session.state or {})
    if state.get("turn") != "sheep" or state.get("player_side") != "sheep":
        return
    if dest not in game.sheep_moves(state["sheep"], state["wolves"]):
        return

    state["sheep"] = dest
    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(callback.message, session_id, state, lang, user, winner)
        return

    # Computer (wolves) turn
    state["turn"] = "wolves"
    await update_session_state(session_id, state, current_turn_user_id=None)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_inactive_keyboard(session_id, state),
    )
    await asyncio.sleep(COMP_MOVE_DELAY)
    await _do_comp_wolves_move(callback.message, session, state, lang, user)


# ── Wolf select (player = wolves, step 1) ─────────────────────────────────────

@router.callback_query(F.data.startswith("sw:ws:"))
async def callback_wolf_select(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    # sw:ws:{session_id}:{wolf_idx}
    session_id, wolf_idx = int(parts[2]), int(parts[3])

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return
    if session.created_by_user_id != user.id:
        return

    state = dict(session.state or {})
    if state.get("turn") != "wolves" or state.get("player_side") != "wolves":
        return
    if not game.wolf_moves_for(wolf_idx, state["wolves"], state["sheep"]):
        return  # that wolf has no valid moves

    state["selected_wolf"] = wolf_idx
    await update_session_state(session_id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_active_keyboard(session_id, state),
    )


# ── Wolf move (player = wolves, step 2) ──────────────────────────────────────

@router.callback_query(F.data.startswith("sw:wm:"))
async def callback_wolf_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    parts = callback.data.split(":")
    # sw:wm:{session_id}:{wolf_idx}:{r}:{c}
    session_id, wolf_idx, r, c = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
    dest = [r, c]

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        return
    if session.created_by_user_id != user.id:
        return

    state = dict(session.state or {})
    if state.get("turn") != "wolves" or state.get("player_side") != "wolves":
        return
    if dest not in game.wolf_moves_for(wolf_idx, state["wolves"], state["sheep"]):
        return

    state["wolves"][wolf_idx] = dest
    state["selected_wolf"] = None
    winner = game.check_winner(state["sheep"], state["wolves"])
    if winner:
        await _finish_game(callback.message, session_id, state, lang, user, winner)
        return

    # Computer (sheep) turn
    state["turn"] = "sheep"
    await update_session_state(session_id, state, current_turn_user_id=None)
    await callback.message.edit_text(
        render_status(state, lang),
        reply_markup=_inactive_keyboard(session_id, state),
    )
    await asyncio.sleep(COMP_MOVE_DELAY)
    await _do_comp_sheep_move(callback.message, session, state, lang, user)

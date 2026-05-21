from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.mastermind import game
from app.games.mastermind.game import DIFFICULTY
from app.games.mastermind.keyboards import cmplx_keyboard, game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.services.sessions import (
    create_solo_session,
    finish_session,
    get_game_streak_line,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import update_user_settings, upsert_user
from app.handlers.common import get_game_keyboard

router = Router()

BLANK = "⬛"

_MA_TO_VARIANT = {10: "easy", 12: "normal", 18: "hard"}

def render_text(lang: dict, state: dict, final: str | None = None) -> str:
    size = state["size"]
    colors = state["colors"]
    n_colors = len(colors)
    title = f"{lang['icon-mastermind']} {lang['game-mastermind']} · {n_colors} {lang['mm-colors']} {lang['mm-on']} {size} {lang['mm-positions']}"

    lines = [title, ""]
    for entry in state["history"]:
        guess_str = "".join(entry["guess"])
        feedback = "⚫" * entry["bulls"] + "⚪" * entry["cows"]
        lines.append(f"{guess_str}  →  {feedback or '—'}")
    lines.append("")

    if final == "win":
        lines.append(lang["game-win"])
    elif final == "loss":
        lines.append(lang["game-lose"])
        lines.append(f"{lang['mm-secret']} {''.join(state['secret'])}")
    else:
        current = state["current"]
        current_str = "".join(current) + BLANK * (size - len(current))
        attempt = len(state["history"]) + 1
        lines.append(current_str)
        lines.append(f"{lang['mm-attempt']} {attempt} / {state['max_attempts']}")

    return "\n".join(lines)

def _mm_menu_text(lang: dict, user_settings: dict | None) -> str:
    cmplx = (user_settings or {}).get("mastermind_cmplx", "easy")
    return f"{lang['icon-mastermind']} *{lang['game-mastermind']}*\n{lang['setting-cmplx']}: {lang[f'cmplx-{cmplx}']}"

async def open_mastermind_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    streak = await get_game_streak_line(user.id, game.code, lang)
    await message.answer(_mm_menu_text(lang, user.settings) + streak, reply_markup=get_game_keyboard(game.code, lang, chat_type=message.chat.type))

async def start_mastermind_game(message: Message, user, lang, difficulty: str, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(difficulty=difficulty)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(render_text(lang, session.state), reply_markup=game_keyboard(session.id, session.state, True, lang))

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    difficulty = (user.settings or {}).get("mastermind_cmplx", "easy")
    await start_mastermind_game(callback.message, user, lang, difficulty, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(GameCallbackFilter("cmplx", game.code))
async def menu_cmplx(callback: CallbackQuery, user, lang) -> None:
    cmplx = (user.settings or {}).get("mastermind_cmplx", "easy")
    text = f"{lang['chus-cmplx']}\n\n{lang['setting-cmplx']}: {lang[f'cmplx-{cmplx}']}"
    await safe_edit(callback.message, text, reply_markup=cmplx_keyboard(lang, "game:mastermind"))
    await callback.answer()

@router.callback_query(F.data == "mm:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("mm:cmplx:"))
async def callback_cmplx(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    difficulty = callback.data.split(":")[2]
    if difficulty not in DIFFICULTY:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"mastermind_cmplx": difficulty, "current_game": game.code})
    updated = dict(user.settings or {})
    updated["mastermind_cmplx"] = difficulty
    await safe_edit(callback.message, _mm_menu_text(lang, updated), reply_markup=get_game_keyboard(game.code, lang, chat_type=callback.message.chat.type))

@router.callback_query(F.data.startswith("mm:color:"))
async def callback_color(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    session_id = int(parts[2])
    color_idx = int(parts[3])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    color = state["colors"][color_idx]
    state = game.add_color(state, color)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

@router.callback_query(F.data.startswith("mm:back:"))
async def callback_back(callback: CallbackQuery) -> None:
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
    state = game.backspace(state)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

@router.callback_query(F.data.startswith("mm:submit:"))
async def callback_submit(callback: CallbackQuery) -> None:
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
    result = game.submit_guess(state)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        await finish_session(session.id, state, winner_user_id=user.id if result["state"] == "win" else None)
        await record_game_result(user.id, game.code, result["state"], variant_key=_MA_TO_VARIANT.get(state["max_attempts"], "easy"))
        menu_msg_id = state.get("menu_message_id")
        await callback.message.edit_text(
            render_text(lang, state, final=result["state"]),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_mastermind_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

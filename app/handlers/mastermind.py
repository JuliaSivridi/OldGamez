from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.mastermind import game
from app.games.mastermind.game import DIFFICULTY
from app.games.mastermind.keyboards import cmplx_keyboard, game_keyboard
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

BLANK = "⬛"


def mastermind_menu_keyboard(lang, chat_type=None):
    return game_menu_keyboard(lang, game_code=game.code, extra_setting_key="cmplx", chat_type=chat_type)


def render_text(lang: dict, state: dict, final: str | None = None) -> str:
    size = state["size"]
    colors = state["colors"]
    n_colors = len(colors)
    title = f"{lang['game-mastermind']} · {n_colors} {lang['mm-colors']} {lang['mm-on']} {size} {lang['mm-positions']}"

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
    return f"{lang['game-mastermind']}\n{lang['setting-cmplx']}: {lang[f'cmplx-{cmplx}']}"


async def open_mastermind_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(_mm_menu_text(lang, user.settings), reply_markup=mastermind_menu_keyboard(lang, chat_type=message.chat.type))


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


@router.message(Command("mastermind"))
async def cmd_mastermind(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_mastermind_menu(message, user, lang)


@router.callback_query(F.data == "game:mastermind")
async def open_mastermind_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, _mm_menu_text(lang, user.settings), reply_markup=mastermind_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


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


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses"])
    await safe_edit(callback.message, text, reply_markup=mastermind_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-mastermind"], reply_markup=mastermind_menu_keyboard(lang, chat_type=callback.message.chat.type))
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
    await safe_edit(callback.message, _mm_menu_text(lang, updated), reply_markup=mastermind_menu_keyboard(lang, chat_type=callback.message.chat.type))


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
        await record_game_result(user.id, game.code, result["state"])
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

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.bullscows import game
from app.games.bullscows.keyboards import game_keyboard, size_keyboard
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


def bullscows_menu_keyboard(lang, chat_type=None):
    return game_menu_keyboard(lang, game_code=game.code, extra_setting_key="size", chat_type=chat_type)


def render_text(lang: dict, state: dict, final: str | None = None) -> str:
    size = state["size"]
    title = f"{lang['game-bullscows']} · {size} {lang['bc-digits']}"

    lines = [title, ""]
    for entry in state["history"]:
        guess_str = " ".join(str(d) for d in entry["guess"])
        feedback = "🐂" * entry["bulls"] + "🐄" * entry["cows"]
        lines.append(f"{guess_str}  →  {feedback or '—'}")
    lines.append("")

    if final == "win":
        lines.append(lang["game-win"])
    elif final == "loss":
        lines.append(lang["game-lose"])
        lines.append(f"{lang['bc-secret']} {' '.join(str(d) for d in state['secret'])}")
    else:
        current = state["current"]
        slots = [str(d) for d in current] + ["_"] * (size - len(current))
        current_str = " ".join(slots)
        attempt = len(state["history"]) + 1
        lines.append(f"`{current_str}`")
        lines.append(f"{lang['bc-attempt']} {attempt} / {state['max_attempts']}")

    return "\n".join(lines)


def _bc_menu_text(lang: dict, user_settings: dict | None) -> str:
    size = int((user_settings or {}).get("bullscows_size", 4))
    return f"{lang['game-bullscows']}\n{lang['setting-size']}: {size}"


async def open_bullscows_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(_bc_menu_text(lang, user.settings), reply_markup=bullscows_menu_keyboard(lang, chat_type=message.chat.type))


async def start_bullscows_game(message: Message, user, lang, size: int, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(size=size)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(render_text(lang, session.state), reply_markup=game_keyboard(session.id, session.state, True, lang))


@router.message(Command("bullscows"))
async def cmd_bullscows(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_bullscows_menu(message, user, lang)


@router.callback_query(F.data == "game:bullscows")
async def open_bullscows_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, _bc_menu_text(lang, user.settings), reply_markup=bullscows_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("bullscows_size", 4))
    await start_bullscows_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("size", game.code))
async def menu_size(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("bullscows_size", 4))
    text = f"{lang['chus-size']}\n\n{lang['setting-size']}: {lang[str(size)]}"
    await safe_edit(callback.message, text, reply_markup=size_keyboard(lang, "game:bullscows"))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses"])
    await safe_edit(callback.message, text, reply_markup=bullscows_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-bullscows"], reply_markup=bullscows_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "bc:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("bc:size:"))
async def callback_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"bullscows_size": size, "current_game": game.code})
    updated = dict(user.settings or {})
    updated["bullscows_size"] = size
    await safe_edit(callback.message, _bc_menu_text(lang, updated), reply_markup=bullscows_menu_keyboard(lang, chat_type=callback.message.chat.type))


@router.callback_query(F.data.startswith("bc:digit:"))
async def callback_digit(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    session_id = int(parts[2])
    digit = int(parts[3])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    state = game.add_digit(state, digit)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))


@router.callback_query(F.data.startswith("bc:back:"))
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
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))


@router.callback_query(F.data.startswith("bc:submit:"))
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
        await open_bullscows_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

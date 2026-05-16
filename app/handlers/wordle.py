from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.wordle import game
from app.games.wordle.game import MARK_EMOJI
from app.games.wordle.keyboards import game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack, normalize_language_code
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


def wordle_menu_keyboard(lang, chat_type=None):
    return game_menu_keyboard(lang, game_code=game.code, chat_type=chat_type)


def render_text(lang: dict, state: dict, final: str | None = None) -> str:
    size = state["size"]
    title = f"{lang['game-wordle']} · {size} {lang['wrd-letters']}"

    lines = [title, ""]
    for entry in state["history"]:
        guess_line = "   ".join(entry["guess"])
        marks_line = "  ".join(MARK_EMOJI[m] for m in entry["marks"])
        lines.append(f"<code>{guess_line}</code>")
        lines.append(marks_line)
        lines.append("")

    if final == "win":
        lines.append(lang["game-win"])
    elif final == "loss":
        lines.append(lang["game-lose"])
        lines.append(f"{lang['wrd-secret']} <code>{'   '.join(state['word'])}</code>")
    else:
        current = state["current"]
        slots = list(current) + ["_"] * (size - len(current))
        current_str = "   ".join(slots)
        attempt = len(state["history"]) + 1
        lines.append(f"<code>{current_str}</code>")
        lines.append(f"{lang['wrd-attempt']} {attempt} / {state['max_attempts']}")

    return "\n".join(lines)


async def open_wordle_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-wordle"], reply_markup=wordle_menu_keyboard(lang, chat_type=message.chat.type))


async def start_wordle_game(message: Message, user, lang, lang_code: str, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(lang_code=lang_code)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        render_text(lang, session.state),
        reply_markup=game_keyboard(session.id, session.state, True, lang),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("wordle"))
async def cmd_wordle(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_wordle_menu(message, user, lang)


@router.callback_query(F.data == "game:wordle")
async def open_wordle_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, lang["game-wordle"], reply_markup=wordle_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    lang_code = normalize_language_code(user.language_code)
    await start_wordle_game(callback.message, user, lang, lang_code, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses"])
    await safe_edit(callback.message, text, reply_markup=wordle_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-wordle"], reply_markup=wordle_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "wrd:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("wrd:letter:"))
async def callback_letter(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    session_id = int(parts[2])
    letter = parts[3]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    state = game.add_letter(state, letter)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("wrd:back:"))
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
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("wrd:submit:"))
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
            reply_markup=game_keyboard(session.id, state, False, lang),
            parse_mode=ParseMode.HTML,
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_wordle_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang), parse_mode=ParseMode.HTML)

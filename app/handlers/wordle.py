from aiogram import F, Router
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


def render_text(lang: dict, state: dict, final: str | None = None, invalid: bool = False) -> str:
    size = state["size"]
    title = f"{lang['game-wordle']} · {size} {lang['wrd-letters']}"

    lines = [title, ""]
    for entry in state["history"]:
        pairs = " ".join(f"{l}{MARK_EMOJI[m]}" for l, m in zip(entry["guess"], entry["marks"]))
        lines.append(pairs)
        lines.append("")

    if final == "win":
        lines.append(lang["game-win"])
    elif final == "loss":
        lines.append(lang["game-lose"])
        lines.append(f"{lang['wrd-secret']} {' '.join(state['word'])}")
    else:
        current = state["current"]
        current_str = " ".join(s if s is not None else "_" for s in current)
        attempt = len(state["history"]) + 1
        lines.append(f"`{current_str}`")
        lines.append(f"{lang['wrd-attempt']} {attempt} / {state['max_attempts']}")
        if invalid:
            lines.append(lang["wrd-invalid"])

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
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))


@router.callback_query(F.data.startswith("wrd:hint:"))
async def callback_hint(callback: CallbackQuery) -> None:
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
    state = game.apply_hint(state)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))


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
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))


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
    if result["state"] == "invalid":
        await update_session_state(session.id, state, current_turn_user_id=user.id)
        await safe_edit(callback.message, render_text(lang, state, invalid=True), reply_markup=game_keyboard(session.id, state, True, lang))
        return
    if result["state"] in ("win", "loss"):
        await finish_session(session.id, state, winner_user_id=user.id if result["state"] == "win" else None)
        await record_game_result(user.id, game.code, result["state"])
        menu_msg_id = state.get("menu_message_id")
        await callback.message.edit_text(
            render_text(lang, state, final=result["state"]),
            reply_markup=game_keyboard(session.id, state, False, lang),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_wordle_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

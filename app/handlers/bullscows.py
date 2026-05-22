from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.games.bullscows import game
from app.games.bullscows.keyboards import game_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit, validate_session
from app.services.sessions import (
    create_solo_session,
    finish_session,
    record_game_result,
    update_session_state,
    xp_gain_line,
)
from app.handlers.common import open_game_menu

router = Router()

_BC_SIZE_TO_VARIANT = {4: "easy", 5: "normal", 6: "hard"}

def render_text(lang: dict, state: dict, final: str | None = None) -> str:
    size = state["size"]
    title = f"{lang['icon-bullscows']} {lang['game-bullscows']} · {size} {lang['bc-digits']}"

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

async def open_bullscows_menu(message: Message, user, lang) -> None:
    await open_game_menu(message, user, lang, game.code)

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

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("bullscows_size", 4))
    await start_bullscows_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == "bc:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("bc:digit:"))
async def callback_digit(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    session_id = int(parts[2])
    digit = int(parts[3])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    state = game.add_digit(state, digit)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

@router.callback_query(F.data.startswith("bc:back:"))
async def callback_back(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[2])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    state = game.backspace(state)
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await safe_edit(callback.message, render_text(lang, state), reply_markup=game_keyboard(session.id, state, True, lang))

@router.callback_query(F.data.startswith("bc:submit:"))
async def callback_submit(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[2])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    result = game.submit_guess(state)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        await finish_session(session.id, state, winner_user_id=user.id if result["state"] == "win" else None)
        xp = await record_game_result(user.id, game.code, result["state"], variant_key=_BC_SIZE_TO_VARIANT.get(state["size"], "easy"))
        menu_msg_id = state.get("menu_message_id")
        await callback.message.edit_text(
            render_text(lang, state, final=result["state"]) + xp_gain_line(xp, lang),
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

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.games.minesweeper import game
from app.games.minesweeper.keyboards import field_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import validate_session
from app.i18n.translator import get_language_pack
from app.services.sessions import (
    create_solo_session,
    finish_session,
    get_active_solo_session,
    record_game_result,
    update_session_state,
    xp_gain_line,
)
from app.services.users import upsert_user
from app.handlers.common import open_game_menu

router = Router()

def render_game_text(lang: dict[str, str], state: dict) -> str:
    return (
        f"{lang['icon-mines']} {lang['game-mines']} | {lang['mines-regime']}"
        f"{lang['mode-dig'] if state['is_dig'] else lang['mode-flag']}\n"
        f"{lang['mines-count']}{state['mines_count']} | {lang['mines-mark']}{game.count_marks(state['cover'])}"
    )

async def start_minesweeper_game(message: Message, user, lang: dict[str, str], mines_count: int, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(mines_count=mines_count)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        render_game_text(lang, session.state),
        reply_markup=field_keyboard(lang, session.state, session.id, game_over=False),
    )

_MINES_TO_VARIANT = {8: "easy", 12: "normal", 16: "hard"}

async def open_minesweeper_menu(message: Message, user, lang) -> None:
    await open_game_menu(message, user, lang, game.code)

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    mines_count = int((user.settings or {}).get("minesweeper_mines", 12))
    await start_minesweeper_game(callback.message, user, lang, mines_count, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == "msw:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("msw:switch:"))
async def callback_switch_mode(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    mode = callback.data.split(":")[2]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    session_id = None
    session = await get_active_solo_session(user.id, game.code)
    if session is None:
        return
    session_id = session.id
    state = dict(session.state)
    state["is_dig"] = mode == "dig"
    await update_session_state(session_id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_game_text(lang, state),
        reply_markup=field_keyboard(lang, state, session_id, game_over=False),
    )

@router.callback_query(F.data.startswith("msw:dig:"))
@router.callback_query(F.data.startswith("msw:flag:"))
async def callback_move(callback: CallbackQuery) -> None:
    _, action, session_id_text, x_text, y_text = callback.data.split(":")
    session_id = int(session_id_text)
    x = int(x_text)
    y = int(y_text)
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    menu_msg_id = state.get("menu_message_id")

    if action == "dig":
        result = game.handle_dig(state, x, y)
    else:
        result = game.handle_flag(state, x, y)
    state = result["game_state"]

    if result["state"] == "loss":
        await finish_session(session.id, state, winner_user_id=None)
        xp = await record_game_result(user.id, game.code, "loss", variant_key=_MINES_TO_VARIANT.get(state["mines_count"], "normal"))
        await callback.message.edit_text(
            lang["game-lose"] + xp_gain_line(xp, lang),
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_minesweeper_menu(callback.message, user, lang)
        return

    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        xp = await record_game_result(user.id, game.code, "win", variant_key=_MINES_TO_VARIANT.get(state["mines_count"], "normal"))
        await callback.message.edit_text(
            lang["game-win"] + xp_gain_line(xp, lang),
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_minesweeper_menu(callback.message, user, lang)
        return

    await update_session_state(session.id, state, current_turn_user_id=user.id)
    if action == "dig":
        await callback.message.edit_reply_markup(
            reply_markup=field_keyboard(lang, state, session.id, game_over=False),
        )
    else:
        await callback.message.edit_text(
            render_game_text(lang, state),
            reply_markup=field_keyboard(lang, state, session.id, game_over=False),
        )

import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.games.lightsout import game
from app.games.lightsout.keyboards import board_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import validate_session
from app.services.sessions import (
    create_solo_session,
    finish_session,
    record_game_result,
    update_session_state,
)
from app.handlers.common import open_game_menu

router = Router()

async def start_lightsout_game(message: Message, user, lang: dict[str, str], size: int, menu_message_id: int | None = None) -> None:
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
        f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
        reply_markup=board_keyboard(session.id, session.state["cells"], size, True, lang),
    )

async def open_lightsout_menu(message: Message, user, lang) -> None:
    await open_game_menu(message, user, lang, game.code)

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("lightsout_size", 5))
    await start_lightsout_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == "lto:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("lto:press:"))
async def callback_press(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    _, _, session_id_text, idx_text = callback.data.split(":")
    session_id = int(session_id_text)
    idx = int(idx_text)
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    menu_msg_id = state.get("menu_message_id")
    result = game.press(state, idx)
    state = result["game_state"]
    size = state["size"]
    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win", variant_key=str(state["size"]), best_score=state.get("taps", 0))
        await callback.message.edit_text(
            lang["game-win"],
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_lightsout_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
        reply_markup=board_keyboard(session.id, state["cells"], size, True, lang),
    )

@router.callback_query(F.data.startswith("lto:give_up:"))
async def callback_give_up(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    session_id = int(callback.data.split(":")[2])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    menu_msg_id = state.get("menu_message_id")
    await finish_session(session.id, state, winner_user_id=None)
    await record_game_result(user.id, game.code, "loss", variant_key=str(state["size"]))
    await callback.message.edit_text(
        lang["game-lose"],
    )
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_lightsout_menu(callback.message, user, lang)

@router.callback_query(F.data.startswith("lto:solve:"))
async def callback_solve(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    session_id = int(callback.data.split(":")[2])
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    size = state["size"]
    menu_msg_id = state.get("menu_message_id")
    solution = game.solve(state)

    for idx in solution:
        await asyncio.sleep(1)
        result = game.press(state, idx)
        state = result["game_state"]
        await callback.message.edit_text(
            f"{lang['icon-lightsout']} {lang['game-lightsout']} {size}×{size}",
            reply_markup=board_keyboard(session.id, state["cells"], size, False),  # animation step
        )

    await callback.message.edit_text(lang["game-win"])
    await finish_session(session.id, state, winner_user_id=None)
    # No stat recorded — solver was used
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_lightsout_menu(callback.message, user, lang)

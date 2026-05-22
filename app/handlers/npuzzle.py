from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.games.npuzzle import game
from app.games.npuzzle.keyboards import tiles_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import validate_session
from app.services.sessions import create_solo_session, finish_session, record_game_result, update_session_state, xp_gain_line
from app.handlers.common import open_game_menu

router = Router()

async def start_npuzzle_game(message: Message, user, lang: dict[str, str], size: int, menu_message_id: int | None = None) -> None:
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
        f"{lang['icon-npuzzle']} {lang['game-npuzzle']} {size}x{size}",
        reply_markup=tiles_keyboard(session.id, session.state["tiles"], size, active=True, lang=lang),
    )

async def open_npuzzle_menu(message: Message, user, lang) -> None:
    await open_game_menu(message, user, lang, game.code)

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("npuzzle_size", 3))
    await start_npuzzle_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == "npz:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("npz:move:"))
async def callback_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    _, _, session_id_text, tile_index_text = callback.data.split(":")
    session_id = int(session_id_text)
    tile_index = int(tile_index_text)
    result = await validate_session(callback, session_id)
    if result is None:
        return
    user, lang, session, state = result
    menu_msg_id = state.get("menu_message_id")
    result = game.move(state, tile_index)
    state = result["game_state"]
    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        xp = await record_game_result(user.id, game.code, "win", variant_key=str(state["size"]), best_score=state.get("moves", 0))
        await callback.message.edit_text(
            lang["game-win"] + xp_gain_line(xp, lang),
            reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"], active=False),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_npuzzle_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        f"{lang['icon-npuzzle']} {lang['game-npuzzle']} {state['size']}x{state['size']}",
        reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"], active=True, lang=lang),
    )

@router.callback_query(F.data.startswith("npz:give_up:"))
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
    xp = await record_game_result(user.id, game.code, "loss", variant_key=str(state["size"]))
    await callback.message.edit_text(
        lang["game-lose"] + xp_gain_line(xp, lang),
        reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"], active=False),
    )
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_npuzzle_menu(callback.message, user, lang)


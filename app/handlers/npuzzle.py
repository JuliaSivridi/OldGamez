from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionStatus
from app.games.npuzzle import game
from app.games.npuzzle.keyboards import size_keyboard, tiles_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.services.sessions import create_solo_session, finish_session, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user
from app.handlers.common import get_game_keyboard

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

def _npz_menu_text(lang: dict, user_settings: dict | None) -> str:
    size = int((user_settings or {}).get("npuzzle_size", 3))
    return f"{lang['icon-npuzzle']} *{lang['game-npuzzle']}*\n{lang['setting-size']}: {lang[str(size)]}{lang['sep-x']}{lang[str(size)]}"

async def open_npuzzle_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _npz_menu_text(lang, user.settings),
        reply_markup=get_game_keyboard(game.code, lang, chat_type=message.chat.type),
    )

@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("npuzzle_size", 3))
    await start_npuzzle_game(callback.message, user, lang, size, menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(GameCallbackFilter("size", game.code))
async def menu_size(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("npuzzle_size", 3))
    cur = f"{lang[str(size)]}{lang['sep-x']}{lang[str(size)]}"
    text = f"{lang['chus-size']}\n\n{lang['setting-size']}: {cur}"
    await safe_edit(callback.message, text, reply_markup=size_keyboard(lang, "game:npuzzle"))
    await callback.answer()

@router.callback_query(F.data == "npz:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()

@router.callback_query(F.data.startswith("npz:size:"))
async def callback_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"npuzzle_size": size, "current_game": game.code})
    updated = dict(user.settings or {})
    updated["npuzzle_size"] = size
    await safe_edit(
        callback.message,
        _npz_menu_text(lang, updated),
        reply_markup=get_game_keyboard(game.code, lang, chat_type=callback.message.chat.type),
    )

@router.callback_query(F.data.startswith("npz:move:"))
async def callback_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    _, _, session_id_text, tile_index_text = callback.data.split(":")
    session_id = int(session_id_text)
    tile_index = int(tile_index_text)
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    result = game.move(state, tile_index)
    state = result["game_state"]
    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win", variant_key=str(state["size"]), best_score=state.get("moves", 0))
        await callback.message.edit_text(
            lang["game-win"],
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
    await callback.answer()
    session_id = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    await finish_session(session.id, state, winner_user_id=None)
    await record_game_result(user.id, game.code, "loss", variant_key=str(state["size"]))
    await callback.message.edit_text(
        lang["game-lose"],
        reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"], active=False),
    )
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_npuzzle_menu(callback.message, user, lang)


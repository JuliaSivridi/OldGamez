from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.games.npuzzle import game
from app.games.npuzzle.keyboards import size_keyboard, tiles_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard
from app.services.sessions import create_solo_session, finish_session, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user


class GameCallbackFilter(BaseFilter):
    def __init__(self, action: str, game_code: str):
        self.action = action
        self.game_code = game_code

    async def __call__(self, callback: CallbackQuery):
        if (callback.from_user is None 
            or callback.data is None
            or callback.message is None
        ):
            return False

        expected = f"game:{self.action}:{self.game_code}"
        if callback.data != expected:
            return False

        user = await upsert_user(callback.from_user)
        lang = get_language_pack(user.language_code)

        return {"user": user, "lang": lang}


router = Router()


async def start_npuzzle_game(message: Message, user, lang: dict[str, str], size: int) -> None:
    state = game.new_game_state(size=size)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        f"{lang['game-npuzzle']}{size}x{size}",
        reply_markup=tiles_keyboard(session.id, session.state["tiles"], session.state["size"]),
    )


def npuzzle_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_setting_key="size",
        chat_type=chat_type,
    )


async def open_npuzzle_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-npuzzle"],
        reply_markup=npuzzle_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("npuzzle"))
async def cmd_npuzzle_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_npuzzle_menu(message, user, lang)



@router.callback_query(F.data == "game:npuzzle")
async def open_npuzzle_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_npuzzle_menu(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    size = int((user.settings or {}).get("npuzzle_size", 3))
    await start_npuzzle_game(callback.message, user, lang, size)
    await callback.answer()


@router.callback_query(GameCallbackFilter("size", game.code))
async def menu_size(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["chus-size"], reply_markup=size_keyboard(lang))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    text = await get_npuzzle_stats_text(user.id, lang)
    await callback.message.answer(text, 
        reply_markup=npuzzle_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["help-npuzzle"], 
        reply_markup=npuzzle_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
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
    await callback.message.answer(
        lang["size-saved"],
        reply_markup=npuzzle_menu_keyboard(lang, chat_type=callback.message.chat.type),
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
    if session is None or session.created_by_user_id != user.id or session.status.value != "active":
        return
    state = dict(session.state)
    result = game.move(state, tile_index)
    state = result["game_state"]
    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win")
        await callback.message.edit_text(
            lang["game-win"],
            reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"]),
        )
        await open_npuzzle_menu(callback.message, user, lang)
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        f"{lang['game-npuzzle']}{state['size']}x{state['size']}",
        reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"]),
    )


async def get_npuzzle_stats_text(user_id: int, lang: dict[str, str]) -> str:
    stat = await get_game_stat(user_id, game.code)
    wins = 0 if stat is None else stat.wins
    return lang["stat-ttl"] + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"

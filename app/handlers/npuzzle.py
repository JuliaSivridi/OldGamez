from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.npuzzle import game
from app.games.npuzzle.keyboards import size_keyboard, tiles_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard
from app.services.sessions import create_solo_session, finish_session, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user

class MenuTextFilter(BaseFilter):
    def __init__(self, key: str):
        self.key = key
    async def __call__(self, message: Message):
        if message.from_user is None or message.text is None:
            return False
        user = await upsert_user(message.from_user)
        lang = get_language_pack(user.language_code)
        if message.text == lang[self.key]:
            return {"user": user, "lang": lang}
        return False


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
        f"{lang['game-15']}{size}x{size}",
        reply_markup=tiles_keyboard(session.id, session.state["tiles"], session.state["size"]),
    )


async def open_npuzzle_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-15"], reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-size"))


@router.message(Command("npuzzle"))
async def cmd_npuzzle_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_npuzzle_menu(message, user, lang)


@router.message(MenuTextFilter("menu-15"))
async def cmd_npuzzle_menu(message: Message, user, lang) -> None:
    await open_npuzzle_menu(message, user, lang)


@router.callback_query(F.data == "game:15")
async def open_npuzzle_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_npuzzle_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-new"))
async def menu_new_game(message: Message, user, lang) -> None:
    size = int((user.settings or {}).get("npuzzle_size", 3))
    await start_npuzzle_game(message, user, lang, size)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-size"))
async def menu_size(message: Message, user, lang) -> None:
    await message.answer(lang["chus-size"], reply_markup=size_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-npuzzle"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_npuzzle_stats(message)


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
    await callback.message.answer(lang["size-saved"], reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-size"))


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
        return
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        f"{lang['game-15']}{state['size']}x{state['size']}",
        reply_markup=tiles_keyboard(session.id, state["tiles"], state["size"]),
    )


@router.message(Command("npuzzle_stats"))
async def cmd_npuzzle_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    wins = 0 if stat is None else stat.wins
    await message.answer(
        lang["stat-ttl"] + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`",
        parse_mode="Markdown",
    )


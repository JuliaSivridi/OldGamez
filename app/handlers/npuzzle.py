from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.npuzzle import game
from app.games.npuzzle.keyboards import size_keyboard, tiles_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard
from app.services.sessions import create_solo_session, finish_session, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import update_user_settings, upsert_user

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


@router.message(Command("npuzzle"))
@router.message(F.text.in_({"🧩 N-puzzle", "🧩 Пятнашки"}))
async def cmd_npuzzle(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {"current_game": game.code})
    lang = get_language_pack(user.language_code)
    await message.answer(lang["menu-15"], reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-size"))


@router.message(CurrentGameFilter(game.code), F.text.in_({"🆕 New game", "🆕 Новая игра"}))
async def menu_new_game(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    size = int((user.settings or {}).get("npuzzle_size", 3))
    await start_npuzzle_game(message, user, lang, size)


@router.message(CurrentGameFilter(game.code), F.text.in_({"🔢 Size", "🔢 Размер"}))
async def menu_size(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["chus-size"], reply_markup=size_keyboard(lang))


@router.message(CurrentGameFilter(game.code), F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def menu_help(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["help-npuzzle"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), F.text.in_({"📊 Statistics", "📊 Статистика"}))
async def menu_stats(message: Message) -> None:
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


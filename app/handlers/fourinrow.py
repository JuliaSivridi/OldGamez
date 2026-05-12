import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.fourinrow import game
from app.games.fourinrow.keyboards import SYMBOLS, board_keyboard, drop_keyboard
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


def render_text(lang: dict[str, str], state: dict) -> str:
    if state["status"] == "finished":
        result = state.get("result")
        if result == "win":
            return lang["game-win"]
        if result == "loss":
            return lang["game-lose"]
        return lang["game-draw"]
    current_sign = state["user_sign"] if state["current_turn"] == "user" else state["bot_sign"]
    turn_line = lang["turn-user"] if state["current_turn"] == "user" else lang["turn-comp"]
    return f"{lang['game-four']}\n\n{SYMBOLS[current_sign]} {turn_line}"


def render_drop_text(lang: dict[str, str], sign: int, is_user: bool) -> str:
    return f"{lang['game-four']}\n\n{SYMBOLS[sign]} {lang['turn-user'] if is_user else lang['turn-comp']}"


async def animate_drop(message: Message, session_id: int, board: list[list[int]], sign: int, row: int, col: int, lang: dict[str, str], is_user: bool) -> None:
    for now_row in range(row):
        await asyncio.sleep(0.2)
        try:
            await message.edit_text(
                render_drop_text(lang, sign, is_user),
                reply_markup=drop_keyboard(session_id, board, sign, row, now_row, col),
            )
        except TelegramBadRequest:
            pass


async def start_four_game(message: Message, user, lang: dict[str, str]) -> None:
    state = game.new_game_state()
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        render_text(lang, session.state),
        reply_markup=board_keyboard(
            session.id,
            session.state["board"],
            True,
            [session.state["last_move"]] if session.state.get("last_move") else [],
        ),
    )


async def open_four_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-four"], reply_markup=game_menu_keyboard(lang))


@router.message(Command("fourinrow"))
async def cmd_four_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_four_menu(message, user, lang)


@router.message(MenuTextFilter("menu-four"))
async def cmd_four_menu(message: Message, user, lang) -> None:
    await open_four_menu(message, user, lang)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-new"))
async def menu_new_game(message: Message, user, lang) -> None:
    await start_four_game(message, user, lang)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-four"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_four_stats(message)


@router.callback_query(F.data == "fir:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("fir:col:"))
async def callback_col(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    _, _, session_id_text, col_text = callback.data.split(":")
    session_id = int(session_id_text)
    col = int(col_text)
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status.value != "active":
        return
    state = dict(session.state)
    user_result = game.process_turn(state, state["user_sign"], col, True)
    state = user_result["game_state"]
    user_row, user_col = state["last_move"]
    await animate_drop(callback.message, session.id, state["board"], state["user_sign"], user_row, user_col, lang, True)
    if user_result["state"] in {"win", "draw"}:
        state["result"] = user_result["state"]
        await finish_session(session.id, state, winner_user_id=user.id if user_result["state"] == "win" else None)
        await record_game_result(user.id, game.code, "win" if user_result["state"] == "win" else "draw")
        await callback.message.edit_text(
            render_text(lang, state),
            reply_markup=board_keyboard(session.id, state["board"], False, user_result["line"]),
        )
        return

    state["current_turn"] = "bot"
    await callback.message.edit_text(
        render_text(lang, state),
        reply_markup=board_keyboard(session.id, state["board"], False, user_result["line"]),
    )
    await asyncio.sleep(1)
    bot_col = game.get_smart_move(state["board"], state["bot_sign"], state["user_sign"])
    bot_result = game.process_turn(state, state["bot_sign"], bot_col, False)
    state = bot_result["game_state"]
    bot_row, bot_col = state["last_move"]
    await animate_drop(callback.message, session.id, state["board"], state["bot_sign"], bot_row, bot_col, lang, False)
    if bot_result["state"] in {"loss", "draw"}:
        state["result"] = bot_result["state"]
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, "loss" if bot_result["state"] == "loss" else "draw")
        await callback.message.edit_text(
            render_text(lang, state),
            reply_markup=board_keyboard(session.id, state["board"], False, bot_result["line"]),
        )
        return

    state["current_turn"] = "user"
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_text(lang, state),
        reply_markup=board_keyboard(session.id, state["board"], True, bot_result["line"]),
    )


@router.message(Command("four_stats"))
async def cmd_four_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        played = wins = losses = draws = 0
    else:
        played, wins, losses, draws = stat.played, stat.wins, stat.losses, stat.draws
    await message.answer(
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(draws).rjust(21 - len(lang['stat-draw']))}`",
        parse_mode="Markdown",
    )

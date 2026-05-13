import asyncio

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.battleship import game
from app.games.battleship.keyboards import SYMBOLS, board_keyboard
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


def render_game_text(lang: dict[str, str], state: dict, is_game_over: bool = False, is_win: bool = False) -> str:
    if is_game_over:
        return lang["game-win"] if is_win else lang["game-lose"]

    lines = [f"{lang['game-sea']}         (\\/)_ (0_0)_ (\\/)"]
    for row in state["user_board"]:
        lines.append("".join(SYMBOLS[cell] for cell in row))

    turn_line = lang["turn-user"] if state["current_turn"] == "user" else lang["turn-comp"]
    turn_icon = "🙂" if state["current_turn"] == "user" else "🤖"
    lines.append("")
    lines.append(f"{turn_icon}{turn_line}")
    return "\n".join(lines)


async def redraw(callback_message: Message, session_id: int, lang: dict[str, str], state: dict, is_game_over: bool = False, is_win: bool = False) -> None:
    await callback_message.edit_text(
        render_game_text(lang, state, is_game_over, is_win),
        reply_markup=board_keyboard(
            session_id,
            state["bot_cover"],
            state["bot_board"],
            is_active=state["current_turn"] == "user" and not is_game_over,
            is_game_over=is_game_over,
        ),
    )


async def run_computer_turns(callback_message: Message, session_id: int, lang: dict[str, str], state: dict) -> tuple[dict, str]:
    while state["current_turn"] == "bot" and state["status"] == "active":
        await asyncio.sleep(1)
        row, col = game.choose_comp_target(state)
        comp_result = game.make_move(state, row, col, is_user=False)
        state = comp_result["game_state"]

        if comp_result["game_over"]:
            await redraw(callback_message, session_id, lang, state, is_game_over=True, is_win=False)
            return state, "loss"

        await redraw(callback_message, session_id, lang, state)

    return state, "play"


async def start_battleship_game(message: Message, user, lang: dict[str, str]) -> None:
    state = game.new_game_state()
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )

    game_message = await message.answer(
        render_game_text(lang, session.state),
        reply_markup=board_keyboard(session.id, session.state["bot_cover"], session.state["bot_board"], session.state["current_turn"] == "user", False),
    )
    state = dict(session.state)
    if state["current_turn"] == "bot":
        state, outcome = await run_computer_turns(game_message, session.id, lang, state)
        if outcome == "loss":
            await finish_session(session.id, state, winner_user_id=None)
            return
        await update_session_state(session.id, state, current_turn_user_id=user.id)


async def open_battleship_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-sea"],
        reply_markup=game_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("battleship"))
async def cmd_battleship_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_battleship_menu(message, user, lang)


@router.message(MenuTextFilter("menu-sea"))
async def cmd_battleship_menu(message: Message, user, lang) -> None:
    await open_battleship_menu(message, user, lang)


@router.callback_query(F.data == "game:sea")
async def open_battleship_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_battleship_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-bot"))
async def menu_new_game(message: Message, user, lang) -> None:
    await start_battleship_game(message, user, lang)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-sea"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_battleship_stats(message)


@router.callback_query(F.data == "sea:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("sea:try:"))
async def callback_shot(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()

    _, _, session_id_text, row_text, col_text = callback.data.split(":")
    session_id = int(session_id_text)
    row = int(row_text)
    col = int(col_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status.value != "active":
        return

    state = dict(session.state)
    if state["current_turn"] != "user" or state["bot_cover"][row][col]:
        return

    user_result = game.make_move(state, row, col, is_user=True)
    state = user_result["game_state"]

    if user_result["game_over"]:
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win")
        await redraw(callback.message, session.id, lang, state, is_game_over=True, is_win=True)
        return

    await redraw(callback.message, session.id, lang, state)
    if state["current_turn"] == "bot":
        state, outcome = await run_computer_turns(callback.message, session.id, lang, state)
        if outcome == "loss":
            await finish_session(session.id, state, winner_user_id=None)
            await record_game_result(user.id, game.code, "loss")
            return

    await update_session_state(session.id, state, current_turn_user_id=user.id if state["status"] == "active" else None)


@router.message(Command("battleship_stats"))
async def cmd_battleship_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        played = wins = losses = 0
    else:
        played, wins, losses = stat.played, stat.wins, stat.losses
    await message.answer(
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`",
        parse_mode="Markdown",
    )

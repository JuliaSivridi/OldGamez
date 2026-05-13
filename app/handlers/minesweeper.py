from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.minesweeper import game
from app.games.minesweeper.keyboards import difficulty_keyboard, field_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.games import game_menu_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import get_user_setting, update_user_settings, upsert_user

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


def render_game_text(lang: dict[str, str], state: dict) -> str:
    return (
        f"{lang['game-mines']} | {lang['mines-regime']}"
        f"{lang['mode-dig'] if state['is_dig'] else lang['mode-flag']}\n"
        f"{lang['mines-count']}{state['mines_count']} | {lang['mines-mark']}{game.count_marks(state['cover'])}"
    )


def render_stat_text(lang: dict[str, str], played: int, wins: int, losses: int) -> str:
    return (
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
    )


async def start_minesweeper_game(message: Message, user, lang: dict[str, str], mines_count: int) -> None:
    state = game.new_game_state(mines_count=mines_count)
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


async def open_minesweeper_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-mines"], reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-cmplx"))


@router.message(Command("minesweeper"))
async def cmd_minesweeper_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_minesweeper_menu(message, user, lang)


@router.message(MenuTextFilter("menu-mines"))
async def cmd_minesweeper_menu(message: Message, user, lang) -> None:
    await open_minesweeper_menu(message, user, lang)


@router.callback_query(F.data == "game:mines")
async def open_minesweeper_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_minesweeper_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-bot"))
async def menu_new_game(message: Message, user, lang) -> None:
    mines_count = int((user.settings or {}).get("minesweeper_mines", 12))
    await start_minesweeper_game(message, user, lang, mines_count)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-cmplx"))
async def menu_difficulty(message: Message, user, lang) -> None:
    await message.answer(lang["chus-cmplx"] + lang["mines-cmplx"], reply_markup=difficulty_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-mines"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_minesweeper_stats(message)


@router.callback_query(F.data == "msw:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("msw:difficulty:"))
async def callback_difficulty(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    mines_count = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"minesweeper_mines": mines_count, "current_game": game.code})
    await callback.message.answer(
        lang["cmplx-saved"],
        reply_markup=game_menu_keyboard(lang, extra_setting_key="menu-cmplx"),
    )


@router.callback_query(F.data.startswith("msw:switch:"))
async def callback_switch_mode(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    mode = callback.data.split(":")[2]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    session_id = None
    # parse from message markup is messy, so use active session by current game
    from app.services.sessions import get_active_solo_session
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
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    _, action, session_id_text, x_text, y_text = callback.data.split(":")
    session_id = int(session_id_text)
    x = int(x_text)
    y = int(y_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id:
        return
    state = dict(session.state)
    if session.status.value != "active":
        return

    if action == "dig":
        result = game.handle_dig(state, x, y)
    else:
        result = game.handle_flag(state, x, y)
    state = result["game_state"]

    if result["state"] == "loss":
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, "loss")
        await callback.message.edit_text(
            lang["game-lose"],
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
        return

    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win")
        await callback.message.edit_text(
            lang["game-win"],
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
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


@router.message(Command("mines_stats"))
async def cmd_minesweeper_stats(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        await message.answer(render_stat_text(lang, 0, 0, 0), parse_mode="Markdown")
        return
    await message.answer(render_stat_text(lang, stat.played, stat.wins, stat.losses), parse_mode="Markdown")

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.filters.current_game import CurrentGameFilter
from app.games.minesweeper import game
from app.games.minesweeper.keyboards import field_keyboard
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


def cmplx_keyboard(lang: dict[str, str]):
    b = InlineKeyboardBuilder()
    for key, value in (
        ("cmplx-easy", 8),
        ("cmplx-norm", 12),
        ("cmplx-hard", 16),
    ):
        b.button(text=lang[key], callback_data=f"msw:cmplx:{value}")
    b.adjust(3)
    return b.as_markup()


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


def minesweeper_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_setting_key="cmplx",
        chat_type=chat_type,
    )


async def open_minesweeper_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-mines"],
        reply_markup=minesweeper_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("minesweeper"))
async def cmd_minesweeper_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_minesweeper_menu(message, user, lang)


@router.callback_query(F.data == "game:mines")
async def open_minesweeper_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_minesweeper_menu(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    mines_count = int((user.settings or {}).get("minesweeper_mines", 12))
    await start_minesweeper_game(callback.message, user, lang, mines_count)
    await callback.answer()


@router.callback_query(GameCallbackFilter("cmplx", game.code))
async def menu_complexity(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["chus-cmplx"], reply_markup=cmplx_keyboard(lang))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    text = await get_minesweeper_stats_text(user.id, lang)
    await callback.message.answer(text, 
        reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["help-mines"], 
        reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type),
        parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "msw:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("msw:cmplx:"))
async def callback_cmplx(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    mines_count = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"minesweeper_mines": mines_count, "current_game": game.code})
    await callback.message.answer(
        lang["cmplx-saved"],
        reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type),
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


async def get_minesweeper_stats_text(user_id: int, lang: dict[str, str]) -> str:
    stat = await get_game_stat(user_id, game.code)
    if stat is None:
        played = wins = losses = 0
    else:
        played, wins, losses = stat.played, stat.wins, stat.losses
    return (
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(losses).rjust(20 - len(lang['stat-lose']))}`"
    )

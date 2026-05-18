from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import SessionStatus
from app.games.minesweeper import game
from app.games.minesweeper.keyboards import field_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.menus import game_menu_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    format_leaderboard_text,
    format_variant_stats_text,
    get_active_solo_session,
    get_all_game_stats,
    get_game_leaderboard,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import get_user_setting, update_user_settings, upsert_user


router = Router()


def cmplx_keyboard(lang: dict[str, str], back_callback: str):
    b = InlineKeyboardBuilder()
    for key, value in (
        ("cmplx-easy", 8),
        ("cmplx-norm", 12),
        ("cmplx-hard", 16),
    ):
        b.button(text=lang[key], callback_data=f"msw:cmplx:{value}")
    b.button(text=lang["main-back"], callback_data=back_callback)
    b.adjust(3, 1)
    return b.as_markup()


def render_game_text(lang: dict[str, str], state: dict) -> str:
    return (
        f"{lang['icon-mines']} {lang['game-mines']} | {lang['mines-regime']}"
        f"{lang['mode-dig'] if state['is_dig'] else lang['mode-flag']}\n"
        f"{lang['mines-count']}{state['mines_count']} | {lang['mines-mark']}{game.count_marks(state['cover'])}"
    )



async def start_minesweeper_game(message: Message, user, lang: dict[str, str], mines_count: int, menu_message_id: int | None = None) -> None:
    state = game.new_game_state(mines_count=mines_count)
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
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


_MINES_TO_CMPLX = {8: "easy", 12: "norm", 16: "hard"}
_MINES_TO_VARIANT = {8: "easy", 12: "normal", 16: "hard"}


def _mines_menu_text(lang: dict, user_settings: dict | None) -> str:
    mines = int((user_settings or {}).get("minesweeper_mines", 12))
    cmplx = _MINES_TO_CMPLX.get(mines, "norm")
    return f"{lang['icon-mines']} *{lang['game-mines']}*\n{lang['setting-cmplx']}: {lang[f'cmplx-{cmplx}']}"


async def open_minesweeper_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _mines_menu_text(lang, user.settings),
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
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, _mines_menu_text(lang, user.settings), reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    mines_count = int((user.settings or {}).get("minesweeper_mines", 12))
    await start_minesweeper_game(callback.message, user, lang, mines_count, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("cmplx", game.code))
async def menu_complexity(callback: CallbackQuery, user, lang) -> None:
    mines = int((user.settings or {}).get("minesweeper_mines", 12))
    cmplx = _MINES_TO_CMPLX.get(mines, "norm")
    text = f"{lang['chus-cmplx']}\n\n{lang['setting-cmplx']}: {lang[f'cmplx-{cmplx}']}"
    await safe_edit(callback.message, text, reply_markup=cmplx_keyboard(lang, "game:mines"))
    await callback.answer()


_DIFFICULTY_ORDER = {"easy": 0, "normal": 1, "hard": 2}


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stats = await get_all_game_stats(user.id, game.code)
    stats.sort(key=lambda s: _DIFFICULTY_ORDER.get(s.variant_key, 9))
    variant_labels = {"easy": lang["stat-easy"], "normal": lang["stat-normal"], "hard": lang["stat-hard"]}
    game_title = f"{lang['icon-stat']} *{lang['game-mines']}*"
    text = game_title + " | " + format_variant_stats_text(stats, lang, variant_labels, ["played", "wins", "losses"])
    await safe_edit(callback.message, text, reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("top", game.code))
async def menu_top(callback: CallbackQuery, user, lang) -> None:
    entries, viewer_entry = await get_game_leaderboard(game.code, viewer_user_id=user.id)
    title = f"*{lang['game-mines']}*"
    text = format_leaderboard_text(entries, title, lang, viewer_entry)
    await safe_edit(callback.message, text, reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, f"{lang['icon-info']} *{lang['game-mines']}* | *{lang['help-ttl']}*\n\n{lang['help-mines']}", reply_markup=minesweeper_menu_keyboard(lang, chat_type=callback.message.chat.type))
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
    updated = dict(user.settings or {})
    updated["minesweeper_mines"] = mines_count
    await safe_edit(
        callback.message,
        _mines_menu_text(lang, updated),
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
    menu_msg_id = state.get("menu_message_id")
    if session.status != SessionStatus.active:
        return

    if action == "dig":
        result = game.handle_dig(state, x, y)
    else:
        result = game.handle_flag(state, x, y)
    state = result["game_state"]

    if result["state"] == "loss":
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, "loss", variant_key=_MINES_TO_VARIANT.get(state["mines_count"], "normal"))
        await callback.message.edit_text(
            lang["game-lose"],
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_minesweeper_menu(callback.message, user, lang)
        return

    if result["state"] == "win":
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win", variant_key=_MINES_TO_VARIANT.get(state["mines_count"], "normal"))
        await callback.message.edit_text(
            lang["game-win"],
            reply_markup=field_keyboard(lang, state, session.id, game_over=True),
        )
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_minesweeper_menu(callback.message, user, lang)
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

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import SessionStatus
from app.games.ropasci import game, rpssl_game
from app.games.ropasci.game import MODE_LABEL
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.menus import game_menu_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    format_game_stats_text,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import update_user_settings, upsert_user

router = Router()

_RPS_MOVES = ["stone", "scissors", "paper"]
_RPSSL_MOVES = ["stone", "scissors", "paper", "lizard", "spock"]


def rps_menu_keyboard(lang, chat_type=None) -> InlineKeyboardMarkup:
    return game_menu_keyboard(lang, game_code=game.code, extra_setting_key="mode", chat_type=chat_type)


def rpssl_menu_keyboard(lang, chat_type=None) -> InlineKeyboardMarkup:
    return game_menu_keyboard(lang, game_code=rpssl_game.code, extra_setting_key="mode", chat_type=chat_type)


def rps_mode_keyboard(game_code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wins_needed, label in [(1, "1/1"), (2, "2/3"), (3, "3/5")]:
        builder.button(text=label, callback_data=f"rps:setmode:{game_code}:{wins_needed}")
    builder.adjust(3)
    return builder.as_markup()


def rps_game_keyboard(session_id: int, moves: list[str], active: bool, lang: dict, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for move in moves:
        cb = f"{prefix}:move:{session_id}:{move}" if active else f"{prefix}:noop"
        builder.button(text=lang[f"rps-{move}"], callback_data=cb)
    row = len(moves) if len(moves) <= 3 else 3
    builder.adjust(row)
    return builder.as_markup()


def render_text(title: str, state: dict, lang: dict, final: str | None = None) -> str:
    mode = MODE_LABEL.get(state["wins_needed"], "?")
    lines = [f"{title} · {mode}", ""]
    for entry in state["history"]:
        u = lang[f"rps-{entry['user']}"]
        c = lang[f"rps-{entry['comp']}"]
        r = lang[f"rps-{entry['result']}"]
        lines.append(f"{r}  {u} — {c}")
    lines.append("")
    lines.append(f"👤 {state['user_wins']}  :  {state['comp_wins']} 🤖")
    if final == "win":
        lines.append(lang["game-win"])
    elif final == "loss":
        lines.append(lang["game-lose"])
    return "\n".join(lines)


async def open_ropasci_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=message.chat.type))


async def open_rpssl_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": rpssl_game.code})
    await message.answer(lang["game-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=message.chat.type))


async def _finish_game(callback: CallbackQuery, session_id: int, state: dict, final: str,
                       title: str, moves: list, prefix: str, lang: dict, user,
                       open_menu_fn) -> None:
    await finish_session(session_id, state, winner_user_id=user.id if final == "win" else None)
    await record_game_result(user.id, state.get("game_code", prefix), final)
    await safe_edit(
        callback.message,
        render_text(title, state, lang, final=final),
        reply_markup=rps_game_keyboard(session_id, moves, False, lang, prefix),
    )
    menu_msg_id = state.get("menu_message_id")
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_menu_fn(callback.message, user, lang)


# ── RPS ──────────────────────────────────────────────────────────────────────

@router.message(Command("rps"))
async def cmd_ropasci_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_ropasci_menu(message, user, lang)


@router.callback_query(F.data == "game:rps")
async def open_ropasci_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, lang["game-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game_rps(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    state = game.new_game_state(wins_needed)
    state["menu_message_id"] = callback.message.message_id
    session = await create_solo_session(user.id, callback.message.chat.id, game.code, state)
    await callback.message.answer(
        render_text(lang["game-rps"], session.state, lang),
        reply_markup=rps_game_keyboard(session.id, _RPS_MOVES, True, lang, "rps"),
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("mode", game.code))
async def menu_rps_mode(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["chus-mode"], reply_markup=rps_mode_keyboard(game.code))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_rps_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
    await safe_edit(callback.message, text, reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_rps_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "rps:noop")
async def rps_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("rps:move:"))
async def callback_rps_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    session_id, move = int(parts[2]), parts[3]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    result = game.make_move(state, move)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        state["game_code"] = game.code
        await _finish_game(callback, session_id, state, result["state"],
                           lang["game-rps"], _RPS_MOVES, "rps", lang, user, open_ropasci_menu)
    else:
        await update_session_state(session_id, state, current_turn_user_id=user.id)
        await safe_edit(callback.message, render_text(lang["game-rps"], state, lang),
                        reply_markup=rps_game_keyboard(session_id, _RPS_MOVES, True, lang, "rps"))


# ── RPSSL ─────────────────────────────────────────────────────────────────────

@router.message(Command("rpssl"))
async def cmd_rpssl_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_rpssl_menu(message, user, lang)


@router.callback_query(F.data == "game:rpssl")
async def open_rpssl_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": rpssl_game.code})
    await safe_edit(callback.message, lang["game-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", rpssl_game.code))
async def menu_new_game_rpssl(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    state = rpssl_game.new_game_state(wins_needed)
    state["menu_message_id"] = callback.message.message_id
    session = await create_solo_session(user.id, callback.message.chat.id, rpssl_game.code, state)
    await callback.message.answer(
        render_text(lang["game-rpssl"], session.state, lang),
        reply_markup=rps_game_keyboard(session.id, _RPSSL_MOVES, True, lang, "rpssl"),
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("mode", rpssl_game.code))
async def menu_rpssl_mode(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["chus-mode"], reply_markup=rps_mode_keyboard(rpssl_game.code))
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", rpssl_game.code))
async def menu_rpssl_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, rpssl_game.code)
    text = format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])
    await safe_edit(callback.message, text, reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", rpssl_game.code))
async def menu_rpssl_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, lang["help-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "rpssl:noop")
async def rpssl_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("rpssl:move:"))
async def callback_rpssl_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    session_id, move = int(parts[2]), parts[3]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    result = rpssl_game.make_move(state, move)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        state["game_code"] = rpssl_game.code
        await _finish_game(callback, session_id, state, result["state"],
                           lang["game-rpssl"], _RPSSL_MOVES, "rpssl", lang, user, open_rpssl_menu)
    else:
        await update_session_state(session_id, state, current_turn_user_id=user.id)
        await safe_edit(callback.message, render_text(lang["game-rpssl"], state, lang),
                        reply_markup=rps_game_keyboard(session_id, _RPSSL_MOVES, True, lang, "rpssl"))


# ── Shared mode setter ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rps:setmode:"))
async def callback_setmode(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    parts = callback.data.split(":")
    game_code, wins_needed = parts[2], int(parts[3])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"rps_mode": wins_needed, "current_game": game_code})
    if game_code == rpssl_game.code:
        await safe_edit(callback.message, lang["game-rpssl"], reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    else:
        await safe_edit(callback.message, lang["game-rps"], reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()

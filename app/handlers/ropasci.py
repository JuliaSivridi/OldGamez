from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import SessionMode, SessionStatus
from app.games.ropasci import game, rpssl_game
from app.games.ropasci.game import MODE_LABEL
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard, group_duel_keyboard
from app.keyboards.menus import game_menu_keyboard
from app.services.duels import (
    broadcast_private_duel_update,
    build_duel_invite_text,
    delete_guest_join_msg,
    get_duel_message_map,
    set_duel_message_ref,
)
from app.services.sessions import (
    activate_group_match_session,
    activate_private_duel_session,
    create_group_match_session,
    create_private_duel_invite,
    create_solo_session,
    finish_session,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import format_player_name, get_user_by_id, update_user_settings, upsert_user

router = Router()

_RPS_MOVES = ["stone", "scissors", "paper"]
_RPSSL_MOVES = ["stone", "scissors", "paper", "lizard", "spock"]


# ── Keyboards ─────────────────────────────────────────────────────────────────

def rps_menu_keyboard(lang, chat_type=None) -> InlineKeyboardMarkup:
    return game_menu_keyboard(lang, game_code=game.code, extra_setting_key="mode",
                               extra_duel_key="duel", extra_group_key="group", chat_type=chat_type)


def rpssl_menu_keyboard(lang, chat_type=None) -> InlineKeyboardMarkup:
    return game_menu_keyboard(lang, game_code=rpssl_game.code, extra_setting_key="mode",
                               extra_duel_key="duel", extra_group_key="group", chat_type=chat_type)


def rps_mode_keyboard(game_code: str, back_callback: str, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wins_needed, label in [(1, "1 / 1"), (2, "2 / 3"), (3, "3 / 5")]:
        builder.button(text=label, callback_data=f"rps:setmode:{game_code}:{wins_needed}")
    builder.button(text=lang["main-back"], callback_data=back_callback)
    builder.adjust(3, 1)
    return builder.as_markup()


def rps_game_keyboard(session_id: int, moves: list[str], active: bool, lang: dict, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for move in moves:
        cb = f"{prefix}:move:{session_id}:{move}" if active else f"{prefix}:noop"
        builder.button(text=lang[f"rps-{move}"], callback_data=cb)
    row = len(moves) if len(moves) <= 3 else 3
    builder.adjust(row)
    return builder.as_markup()


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_text(title: str, state: dict, lang: dict, final: str | None = None) -> str:
    """Solo game."""
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


def render_multi_text(title: str, state: dict, lang: dict,
                      p1_name: str, p2_name: str, final: str | None = None) -> str:
    """Group match — shared neutral view."""
    mode = MODE_LABEL.get(state["wins_needed"], "?")
    lines = [f"{title} · {mode}", ""]
    for entry in state["history"]:
        p1m = lang[f"rps-{entry['p1']}"]
        p2m = lang[f"rps-{entry['p2']}"]
        r = entry["result"]
        if r == "p1_win":
            p1e, p2e = lang["rps-win"], lang["rps-loss"]
        elif r == "p2_win":
            p1e, p2e = lang["rps-loss"], lang["rps-win"]
        else:
            p1e, p2e = lang["rps-draw"], lang["rps-draw"]
        lines.append(f"{p1e}  {p1m} — {p2m}  {p2e}")
    lines.append("")
    p1_wins = state["p1_wins"]
    p2_wins = state["p2_wins"]
    if final == "p1_wins":
        lines.append(f"🏆 {p1_name} {p1_wins} : {p2_wins} {p2_name} 💀")
    elif final == "p2_wins":
        lines.append(f"💀 {p1_name} {p1_wins} : {p2_wins} {p2_name} 🏆")
    else:
        p1_icon = lang["rps-chosen"] if state.get("current_p1") else lang["rps-make-choice"]
        p2_icon = lang["rps-chosen"] if state.get("current_p2") else lang["rps-make-choice"]
        lines.append(f"{p1_name} {p1_wins} : {p2_wins} {p2_name}")
        lines.append(f"{p1_name}: {p1_icon}  |  {p2_name}: {p2_icon}")
    return "\n".join(lines)


def render_duel_text_for_viewer(title: str, state: dict, lang: dict,
                                 viewer_id: int, my_name: str = "", opp_name: str = "",
                                 final: str | None = None) -> str:
    """Private duel — personalized per viewer."""
    mode = MODE_LABEL.get(state["wins_needed"], "?")
    is_p1 = viewer_id == state["p1_id"]
    lines = [f"{title} · {mode}", ""]
    for entry in state["history"]:
        my_move = lang[f"rps-{entry['p1'] if is_p1 else entry['p2']}"]
        opp_move = lang[f"rps-{entry['p2'] if is_p1 else entry['p1']}"]
        r = entry["result"]
        if r == "draw":
            emoji = lang["rps-draw"]
        elif (r == "p1_win") == is_p1:
            emoji = lang["rps-win"]
        else:
            emoji = lang["rps-loss"]
        lines.append(f"{emoji}  {my_move} — {opp_move}")
    lines.append("")
    my_wins = state["p1_wins"] if is_p1 else state["p2_wins"]
    opp_wins = state["p2_wins"] if is_p1 else state["p1_wins"]
    lines.append(f"{my_name} {my_wins} : {opp_wins} {opp_name}")
    if final:
        if (final == "p1_wins") == is_p1:
            lines.append(lang["game-win"])
        else:
            lines.append(lang["game-lose"])
    else:
        my_moved = bool(state["current_p1"] if is_p1 else state["current_p2"])
        opp_moved = bool(state["current_p2"] if is_p1 else state["current_p1"])
        my_icon = lang["rps-chosen"] if my_moved else lang["rps-make-choice"]
        opp_icon = lang["rps-chosen"] if opp_moved else lang["rps-waiting"]
        lines.append(f"{my_name}: {my_icon}  |  {opp_name}: {opp_icon}")
    return "\n".join(lines)


async def _render_rps_duel_for_user(session, user_id: int, title_key: str,
                                     moves: list[str], prefix: str) -> tuple[str, InlineKeyboardMarkup | None]:
    user = await get_user_by_id(user_id)
    lang = get_language_pack(user.language_code if user else "en")
    state = dict(session.state or {})
    is_p1 = user_id == state.get("p1_id")
    p1_user = await get_user_by_id(state.get("p1_id"))
    p2_user = await get_user_by_id(state.get("p2_id"))
    p1_name = format_player_name(p1_user)
    p2_name = format_player_name(p2_user)
    my_name = p1_name if is_p1 else p2_name
    opp_name = p2_name if is_p1 else p1_name
    icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
    if session.status == SessionStatus.finished:
        final = "p1_wins" if state["p1_wins"] >= state["wins_needed"] else "p2_wins"
        text = render_duel_text_for_viewer(f"{lang[icon_key]} {lang[title_key]}", state, lang, user_id,
                                           my_name=my_name, opp_name=opp_name, final=final)
        return text, None
    is_active = not bool(state["current_p1"] if is_p1 else state["current_p2"])
    text = render_duel_text_for_viewer(f"{lang[icon_key]} {lang[title_key]}", state, lang, user_id,
                                       my_name=my_name, opp_name=opp_name, final=None)
    markup = rps_game_keyboard(session.id, moves, is_active, lang, prefix)
    return text, markup


async def _sync_rps_duel_messages(bot, session, title_key: str, moves: list[str], prefix: str) -> None:
    state = dict(session.state or {})
    player_ids = [state.get("p1_id"), state.get("p2_id")]
    await broadcast_private_duel_update(
        bot, player_ids, get_duel_message_map(state),
        lambda uid: _render_rps_duel_for_user(session, uid, title_key, moves, prefix),
    )


# ── Menus ─────────────────────────────────────────────────────────────────────

def _rps_menu_text(lang: dict, user_settings: dict | None, title_key: str, settings_key: str = "rps_mode") -> str:
    wins_needed = int((user_settings or {}).get(settings_key, 1))
    mode_label = MODE_LABEL.get(wins_needed, "?")
    icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
    return f"*{lang[icon_key]} {lang[title_key]}*\n{lang['setting-mode']}: {mode_label}"


def _ropasci_cb_text(lang: dict, user_settings: dict | None) -> str:
    return _rps_menu_text(lang, user_settings, "game-rps")


def _rpssl_cb_text(lang: dict, user_settings: dict | None) -> str:
    return _rps_menu_text(lang, user_settings, "game-rpssl", "rpssl_mode")


async def open_ropasci_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _rps_menu_text(lang, user.settings, "game-rps"),
        reply_markup=rps_menu_keyboard(lang, chat_type=message.chat.type),
    )


async def open_rpssl_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": rpssl_game.code})
    await message.answer(
        _rps_menu_text(lang, user.settings, "game-rpssl", "rpssl_mode"),
        reply_markup=rpssl_menu_keyboard(lang, chat_type=message.chat.type),
    )


# ── Solo finish helper ────────────────────────────────────────────────────────

async def _finish_game(callback: CallbackQuery, session_id: int, state: dict, final: str,
                       title: str, moves: list, prefix: str, lang: dict, user,
                       open_menu_fn) -> None:
    await finish_session(session_id, state, winner_user_id=user.id if final == "win" else None)
    await record_game_result(user.id, state.get("game_code", prefix), final)
    await safe_edit(
        callback.message,
        render_text(title, state, lang, final=final),
    )
    menu_msg_id = state.get("menu_message_id")
    if menu_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
        except Exception:
            pass
    await open_menu_fn(callback.message, user, lang)


# ── Multiplayer helpers ───────────────────────────────────────────────────────

async def _start_rps_duel(message: Message, user, lang, g, wins_needed: int) -> None:
    state = {"wins_needed": wins_needed, "status": "pending", "message_ids": {}}
    session = await create_private_duel_invite(user.id, message.chat.id, g.code, state)
    invite_message = await message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or ""),
    )
    set_duel_message_ref(state, user.id, invite_message)
    await update_session_state(session.id, state, None)


async def _start_rps_group(message: Message, user, lang, g, prefix: str, wins_needed: int,
                            menu_message_id: int | None = None) -> None:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.answer(lang["group-only"])
        return
    state = {"wins_needed": wins_needed, "status": "pending"}
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_group_match_session(user.id, message.chat.id, g.code, state)
    await message.answer(lang["group-wait"],
                         reply_markup=group_duel_keyboard(lang, f"{prefix}:group_join:{session.id}"))


async def _join_rps_private_duel(message: Message, user, lang, session, g,
                                   moves: list[str], prefix: str, menu_kb_fn) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"])
        return
    wins_needed = int(state.get("wins_needed", 1))
    duel_state = g.new_duel_state(wins_needed, session.created_by_user_id, user.id)
    duel_state["message_ids"] = get_duel_message_map(state)

    activated = await activate_private_duel_session(session.id, user.id, duel_state, current_turn_user_id=None)
    if activated is None:
        await message.answer(lang["duel-missing"])
        return

    await update_user_settings(user.id, {"current_game": g.code})
    join_ok_msg = await message.answer(lang["duel-join-ok"], reply_markup=menu_kb_fn(lang, chat_type=message.chat.type))
    duel_state["guest_join_msg"] = {"chat_id": join_ok_msg.chat.id, "message_id": join_ok_msg.message_id}

    host_user = await get_user_by_id(duel_state["p1_id"])
    icon_key = f"icon-{prefix}"
    guest_msg = await message.answer(
        render_duel_text_for_viewer(f"{lang[icon_key]} {lang[f'game-{prefix}']}", duel_state, lang, user.id,
                                    my_name=format_player_name(user),
                                    opp_name=format_player_name(host_user)),
        reply_markup=rps_game_keyboard(activated.id, moves, True, lang, prefix),
    )
    set_duel_message_ref(duel_state, user.id, guest_msg)
    updated = await update_session_state(activated.id, duel_state, None)
    if updated:
        await _sync_rps_duel_messages(message.bot, updated, f"game-{prefix}", moves, prefix)


async def _handle_rps_group_join(callback: CallbackQuery, session_id: int, g, moves: list[str],
                                   prefix: str, title_key: str) -> None:
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.mode != SessionMode.group_match:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return
    if session.created_by_user_id == user.id:
        await callback.answer(lang["duel-self"], show_alert=True)
        return
    if session.status != SessionStatus.pending:
        await callback.answer(lang["duel-full"], show_alert=True)
        return
    player_ids = {p.user_id for p in session.players}
    if user.id in player_ids:
        await callback.answer(lang["group-already-joined"], show_alert=True)
        return
    if len(player_ids) >= 2:
        await callback.answer(lang["duel-full"], show_alert=True)
        return

    original_state = dict(session.state or {})
    wins_needed = int(original_state.get("wins_needed", 1))
    duel_state = g.new_duel_state(wins_needed, session.created_by_user_id, user.id)

    session = await activate_group_match_session(session.id, user.id, duel_state, current_turn_user_id=None)
    if session is None:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return

    p1 = await get_user_by_id(duel_state["p1_id"])
    p2 = await get_user_by_id(duel_state["p2_id"])
    icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
    await callback.message.edit_text(
        render_multi_text(f"{lang[icon_key]} {lang[title_key]}", duel_state, lang, format_player_name(p1), format_player_name(p2)),
        reply_markup=rps_game_keyboard(session.id, moves, True, lang, prefix),
    )
    await callback.answer(lang["duel-join-ok"])


async def _handle_multiplayer_move(callback: CallbackQuery, session, state: dict, user,
                                    move: str, lang: dict, g, moves: list[str],
                                    prefix: str, title_key: str, open_menu_fn, menu_kb_fn) -> None:
    if session.mode == SessionMode.group_match:
        player_ids = {p.user_id for p in session.players}
        if user.id not in player_ids:
            return
    else:
        if user.id not in {state.get("p1_id"), state.get("p2_id")}:
            return

    result = g.make_duel_move(state, user.id, move)
    state = result["game_state"]

    if result["state"] == "already_moved":
        await callback.answer(lang["rps-chosen"], show_alert=True)
        return

    await callback.answer()

    if result["state"] in ("p1_wins", "p2_wins"):
        winner_id = state["p1_id"] if result["state"] == "p1_wins" else state["p2_id"]
        loser_id = state["p2_id"] if result["state"] == "p1_wins" else state["p1_id"]
        await finish_session(session.id, state, winner_user_id=winner_id)
        await record_game_result(winner_id, g.code, "win")
        await record_game_result(loser_id, g.code, "loss")

        _icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
        _title = f"{lang[_icon_key]} {lang[title_key]}"
        if session.mode == SessionMode.group_match:
            p1 = await get_user_by_id(state["p1_id"])
            p2 = await get_user_by_id(state["p2_id"])
            menu_msg_id = state.get("menu_message_id")
            await safe_edit(
                callback.message,
                render_multi_text(_title, state, lang,
                                   format_player_name(p1), format_player_name(p2),
                                   final=result["state"]),
            )
            if menu_msg_id:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
                except Exception:
                    pass
            await open_menu_fn(callback.message, user, lang)
        else:
            refreshed = await get_session_by_id(session.id)
            if refreshed:
                await _sync_rps_duel_messages(callback.bot, refreshed, title_key, moves, prefix)
            await delete_guest_join_msg(callback.bot, state)
            await open_menu_fn(callback.message, user, lang)
            other_id = state["p2_id"] if user.id == state["p1_id"] else state["p1_id"]
            other_user = await get_user_by_id(other_id)
            if other_user:
                other_lang = get_language_pack(other_user.language_code)
                _other_icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
                msg_meta = get_duel_message_map(state).get(str(other_id))
                if msg_meta:
                    try:
                        await callback.bot.send_message(
                            chat_id=msg_meta["chat_id"],
                            text=f"{other_lang[_other_icon_key]} {other_lang[title_key]}",
                            reply_markup=menu_kb_fn(other_lang),
                        )
                    except TelegramBadRequest:
                        pass
    else:  # "waiting" or "round_done"
        _icon_key = "icon-rpssl" if "rpssl" in title_key else "icon-rps"
        _title = f"{lang[_icon_key]} {lang[title_key]}"
        if session.mode == SessionMode.group_match:
            p1 = await get_user_by_id(state["p1_id"])
            p2 = await get_user_by_id(state["p2_id"])
            await update_session_state(session.id, state, None)
            await safe_edit(
                callback.message,
                render_multi_text(_title, state, lang, format_player_name(p1), format_player_name(p2)),
                reply_markup=rps_game_keyboard(session.id, moves, True, lang, prefix),
            )
        else:
            updated = await update_session_state(session.id, state, None)
            if updated:
                await _sync_rps_duel_messages(callback.bot, updated, title_key, moves, prefix)


# ── Public join functions (called from duels.py) ──────────────────────────────

async def join_rps_private_duel(message: Message, user, lang, session) -> None:
    await _join_rps_private_duel(message, user, lang, session, game, _RPS_MOVES, "rps", rps_menu_keyboard)


async def join_rpssl_private_duel(message: Message, user, lang, session) -> None:
    await _join_rps_private_duel(message, user, lang, session, rpssl_game, _RPSSL_MOVES, "rpssl", rpssl_menu_keyboard)


# ── RPS ──────────────────────────────────────────────────────────────────────



@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game_rps(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    state = game.new_game_state(wins_needed)
    state["menu_message_id"] = callback.message.message_id
    session = await create_solo_session(user.id, callback.message.chat.id, game.code, state)
    await callback.message.answer(
        render_text(f"{lang['icon-rps']} {lang['game-rps']}", session.state, lang),
        reply_markup=rps_game_keyboard(session.id, _RPS_MOVES, True, lang, "rps"),
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel_rps(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    await _start_rps_duel(callback.message, user, lang, game, wins_needed)
    await callback.answer()


@router.callback_query(GameCallbackFilter("group", game.code))
async def menu_new_group_rps(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    await _start_rps_group(callback.message, user, lang, game, "rps", wins_needed,
                            menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("mode", game.code))
async def menu_rps_mode(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rps_mode", 1))
    text = f"{lang['chus-mode']}\n\n{lang['setting-mode']}: {MODE_LABEL.get(wins_needed, '?')}"
    await safe_edit(callback.message, text, reply_markup=rps_mode_keyboard(game.code, "game:rps", lang))
    await callback.answer()



@router.callback_query(F.data == "rps:noop")
async def rps_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("rps:group_join:"))
async def callback_rps_group_join(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    session_id = int(callback.data.split(":")[2])
    await _handle_rps_group_join(callback, session_id, game, _RPS_MOVES, "rps", "game-rps")


@router.callback_query(F.data.startswith("rps:move:"))
async def callback_rps_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    parts = callback.data.split(":")
    session_id, move = int(parts[2]), parts[3]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        await callback.answer()
        return
    state = dict(session.state)

    if session.mode in (SessionMode.duel_private, SessionMode.group_match):
        await _handle_multiplayer_move(callback, session, state, user, move, lang,
                                        game, _RPS_MOVES, "rps", "game-rps",
                                        open_ropasci_menu, rps_menu_keyboard)
        return

    await callback.answer()
    if session.created_by_user_id != user.id:
        return
    result = game.make_move(state, move)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        state["game_code"] = game.code
        await _finish_game(callback, session_id, state, result["state"],
                           f"{lang['icon-rps']} {lang['game-rps']}", _RPS_MOVES, "rps", lang, user, open_ropasci_menu)
    else:
        await update_session_state(session_id, state, current_turn_user_id=user.id)
        await safe_edit(callback.message, render_text(f"{lang['icon-rps']} {lang['game-rps']}", state, lang),
                        reply_markup=rps_game_keyboard(session_id, _RPS_MOVES, True, lang, "rps"))


# ── RPSSL ─────────────────────────────────────────────────────────────────────



@router.callback_query(GameCallbackFilter("bot", rpssl_game.code))
async def menu_new_game_rpssl(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rpssl_mode", 1))
    state = rpssl_game.new_game_state(wins_needed)
    state["menu_message_id"] = callback.message.message_id
    session = await create_solo_session(user.id, callback.message.chat.id, rpssl_game.code, state)
    await callback.message.answer(
        render_text(f"{lang['icon-rpssl']} {lang['game-rpssl']}", session.state, lang),
        reply_markup=rps_game_keyboard(session.id, _RPSSL_MOVES, True, lang, "rpssl"),
    )
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", rpssl_game.code))
async def menu_new_duel_rpssl(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rpssl_mode", 1))
    await _start_rps_duel(callback.message, user, lang, rpssl_game, wins_needed)
    await callback.answer()


@router.callback_query(GameCallbackFilter("group", rpssl_game.code))
async def menu_new_group_rpssl(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rpssl_mode", 1))
    await _start_rps_group(callback.message, user, lang, rpssl_game, "rpssl", wins_needed,
                            menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("mode", rpssl_game.code))
async def menu_rpssl_mode(callback: CallbackQuery, user, lang) -> None:
    wins_needed = int((user.settings or {}).get("rpssl_mode", 1))
    text = f"{lang['chus-mode']}\n\n{lang['setting-mode']}: {MODE_LABEL.get(wins_needed, '?')}"
    await safe_edit(callback.message, text, reply_markup=rps_mode_keyboard(rpssl_game.code, "game:rpssl", lang))
    await callback.answer()



@router.callback_query(F.data == "rpssl:noop")
async def rpssl_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("rpssl:group_join:"))
async def callback_rpssl_group_join(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    session_id = int(callback.data.split(":")[2])
    await _handle_rps_group_join(callback, session_id, rpssl_game, _RPSSL_MOVES, "rpssl", "game-rpssl")


@router.callback_query(F.data.startswith("rpssl:move:"))
async def callback_rpssl_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    parts = callback.data.split(":")
    session_id, move = int(parts[2]), parts[3]
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        await callback.answer()
        return
    state = dict(session.state)

    if session.mode in (SessionMode.duel_private, SessionMode.group_match):
        await _handle_multiplayer_move(callback, session, state, user, move, lang,
                                        rpssl_game, _RPSSL_MOVES, "rpssl", "game-rpssl",
                                        open_rpssl_menu, rpssl_menu_keyboard)
        return

    await callback.answer()
    if session.created_by_user_id != user.id:
        return
    result = rpssl_game.make_move(state, move)
    state = result["game_state"]
    if result["state"] in ("win", "loss"):
        state["game_code"] = rpssl_game.code
        await _finish_game(callback, session_id, state, result["state"],
                           f"{lang['icon-rpssl']} {lang['game-rpssl']}", _RPSSL_MOVES, "rpssl", lang, user, open_rpssl_menu)
    else:
        await update_session_state(session_id, state, current_turn_user_id=user.id)
        await safe_edit(callback.message, render_text(f"{lang['icon-rpssl']} {lang['game-rpssl']}", state, lang),
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
    is_rpssl = game_code == rpssl_game.code
    mode_key = "rpssl_mode" if is_rpssl else "rps_mode"
    await update_user_settings(user.id, {mode_key: wins_needed, "current_game": game_code})
    updated_settings = dict(user.settings or {})
    updated_settings[mode_key] = wins_needed
    if is_rpssl:
        await safe_edit(callback.message, _rps_menu_text(lang, updated_settings, "game-rpssl", "rpssl_mode"),
                        reply_markup=rpssl_menu_keyboard(lang, chat_type=callback.message.chat.type))
    else:
        await safe_edit(callback.message, _rps_menu_text(lang, updated_settings, "game-rps"),
                        reply_markup=rps_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()

import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.db.models import SessionMode, SessionStatus
from app.games.battleship import game
from app.games.battleship.keyboards import SYMBOLS, board_keyboard
from app.handlers.filters import GameCallbackFilter
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard
from app.keyboards.menus import game_menu_keyboard
from app.services.duels import broadcast_private_duel_update, build_duel_invite_text, delete_guest_join_msg, get_duel_message_map, set_duel_message_ref
from app.services.sessions import activate_private_duel_session, create_private_duel_invite, create_solo_session, finish_session, format_game_stats_text, get_game_stat, get_session_by_id, record_game_result, update_session_state
from app.services.users import get_user_by_id, update_user_settings, upsert_user


router = Router()


def render_game_text(lang: dict[str, str], state: dict, is_game_over: bool = False, is_win: bool = False) -> str:
    if is_game_over:
        return lang["game-win"] if is_win else lang["game-lose"]

    lines = [f"{lang['icon-sea']} {lang['game-sea']}     (\\/)_(0_0)_(\\/)"]
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
        parse_mode=None,
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


async def start_battleship_game(message: Message, user, lang: dict[str, str], menu_message_id: int | None = None) -> None:
    state = game.new_game_state()
    if menu_message_id:
        state["menu_message_id"] = menu_message_id
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )

    game_message = await message.answer(
        render_game_text(lang, session.state),
        reply_markup=board_keyboard(session.id, session.state["bot_cover"], session.state["bot_board"], session.state["current_turn"] == "user", False),
        parse_mode=None,
    )
    state = dict(session.state)
    if state["current_turn"] == "bot":
        state, outcome = await run_computer_turns(game_message, session.id, lang, state)
        if outcome == "loss":
            await finish_session(session.id, state, winner_user_id=None)
            return
        await update_session_state(session.id, state, current_turn_user_id=user.id)


def battleship_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_duel_key="duel",
        chat_type=chat_type,
    )


def _sea_menu_text(lang: dict) -> str:
    return f"{lang['icon-sea']} *{lang['game-sea']}*"


def render_duel_text_for_viewer(state: dict, lang: dict, viewer_id: int, is_game_over: bool = False) -> str:
    if is_game_over:
        result = state.get("result")
        is_win = (result == "p1_wins" and viewer_id == state["p1_id"]) or \
                 (result == "p2_wins" and viewer_id == state["p2_id"])
        return lang["game-win"] if is_win else lang["game-lose"]

    is_p1 = viewer_id == state["p1_id"]
    own_board = state["p1_board"] if is_p1 else state["p2_board"]
    lines = [f"{lang['icon-sea']} {lang['game-sea']}"]
    for row in own_board:
        lines.append("".join(SYMBOLS[cell] for cell in row))

    is_my_turn = state.get("current_turn_user_id") == viewer_id
    turn_line = lang["turn-user"] if is_my_turn else lang["turn-friend"]
    turn_icon = "🙂" if is_my_turn else "👤"
    lines.append("")
    lines.append(f"{turn_icon} {turn_line}")
    return "\n".join(lines)


async def _render_battleship_duel_for_user(session, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    user = await get_user_by_id(user_id)
    lang = get_language_pack(user.language_code if user else "en")
    state = dict(session.state or {})
    is_game_over = session.status == SessionStatus.finished
    is_p1 = user_id == state.get("p1_id")
    opp_board = state["p2_board"] if is_p1 else state["p1_board"]
    opp_cover = state["p2_cover"] if is_p1 else state["p1_cover"]
    is_active = (not is_game_over) and state.get("current_turn_user_id") == user_id
    text = render_duel_text_for_viewer(state, lang, user_id, is_game_over=is_game_over)
    markup = board_keyboard(session.id, opp_cover, opp_board, is_active, is_game_over)
    return text, markup


async def _sync_battleship_duel_messages(bot, session) -> None:
    state = dict(session.state or {})
    player_ids = [state.get("p1_id"), state.get("p2_id")]
    await broadcast_private_duel_update(
        bot, player_ids, get_duel_message_map(state),
        lambda uid: _render_battleship_duel_for_user(session, uid),
    )


async def join_battleship_duel(message: Message, user, lang, session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"])
        return

    duel_state = game.new_duel_state(session.created_by_user_id, user.id)
    duel_state["message_ids"] = get_duel_message_map(state)

    activated = await activate_private_duel_session(
        session.id, user.id, duel_state,
        current_turn_user_id=duel_state["current_turn_user_id"],
    )
    if activated is None:
        await message.answer(lang["duel-missing"])
        return

    await update_user_settings(user.id, {"current_game": game.code})
    join_ok_msg = await message.answer(lang["duel-join-ok"], reply_markup=battleship_menu_keyboard(lang, chat_type=message.chat.type))
    duel_state["guest_join_msg"] = {"chat_id": join_ok_msg.chat.id, "message_id": join_ok_msg.message_id}

    is_p1 = user.id == duel_state["p1_id"]
    opp_board = duel_state["p2_board"] if is_p1 else duel_state["p1_board"]
    opp_cover = duel_state["p2_cover"] if is_p1 else duel_state["p1_cover"]
    is_active = duel_state["current_turn_user_id"] == user.id

    guest_msg = await message.answer(
        render_duel_text_for_viewer(duel_state, lang, user.id),
        reply_markup=board_keyboard(activated.id, opp_cover, opp_board, is_active, False),
    )
    set_duel_message_ref(duel_state, user.id, guest_msg)
    updated = await update_session_state(activated.id, duel_state, None)
    if updated:
        await _sync_battleship_duel_messages(message.bot, updated)


async def _handle_duel_shot(callback: CallbackQuery, session, user, lang: dict, row: int, col: int) -> None:
    state = dict(session.state)
    if state.get("current_turn_user_id") != user.id:
        await callback.answer()
        return

    is_p1 = user.id == state["p1_id"]
    opp_cover = state["p2_cover"] if is_p1 else state["p1_cover"]
    if opp_cover[row][col]:
        await callback.answer()
        return

    result = game.duel_shot(state, user.id, row, col)
    state = result["game_state"]

    if result["game_over"]:
        winner_id = state["p1_id"] if state["result"] == "p1_wins" else state["p2_id"]
        loser_id = state["p2_id"] if state["result"] == "p1_wins" else state["p1_id"]
        await finish_session(session.id, state, winner_user_id=winner_id)
        await record_game_result(winner_id, game.code, "win")
        await record_game_result(loser_id, game.code, "loss")
        refreshed = await get_session_by_id(session.id)
        if refreshed:
            await _sync_battleship_duel_messages(callback.bot, refreshed)
        await delete_guest_join_msg(callback.bot, state)
        await open_battleship_menu(callback.message, user, lang)
        other_id = state["p2_id"] if is_p1 else state["p1_id"]
        other_user = await get_user_by_id(other_id)
        if other_user:
            other_lang = get_language_pack(other_user.language_code)
            msg_meta = get_duel_message_map(state).get(str(other_id))
            if msg_meta:
                try:
                    await callback.bot.send_message(
                        chat_id=msg_meta["chat_id"],
                        text=_sea_menu_text(other_lang),
                        reply_markup=battleship_menu_keyboard(other_lang),
                    )
                except TelegramBadRequest:
                    pass
        await callback.answer()
        return

    updated = await update_session_state(session.id, state, None)
    if updated:
        await _sync_battleship_duel_messages(callback.bot, updated)
    await callback.answer()


async def open_battleship_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        _sea_menu_text(lang),
        reply_markup=battleship_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("battleship"))
async def cmd_battleship_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_battleship_menu(message, user, lang)


@router.callback_query(F.data == "game:sea")
async def open_battleship_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"current_game": game.code})
    await safe_edit(callback.message, _sea_menu_text(lang), reply_markup=battleship_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_battleship_game(callback.message, user, lang, menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel(callback: CallbackQuery, user, lang) -> None:
    state: dict = {"status": "pending", "message_ids": {}}
    session = await create_private_duel_invite(user.id, callback.message.chat.id, game.code, state)
    invite_message = await callback.message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or ""),
    )
    set_duel_message_ref(state, user.id, invite_message)
    await update_session_state(session.id, state, None)
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    stat = await get_game_stat(user.id, game.code)
    game_title = f"{lang['icon-stat']} *{lang['game-sea']}*"
    text = game_title + " | " + format_game_stats_text(stat, lang, ["played", "wins", "losses"])
    await safe_edit(callback.message, text, reply_markup=battleship_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await safe_edit(callback.message, f"{lang['icon-info']} *{lang['game-sea']}* | *{lang['help-ttl']}*\n\n{lang['help-sea']}", reply_markup=battleship_menu_keyboard(lang, chat_type=callback.message.chat.type))
    await callback.answer()


@router.callback_query(F.data == "sea:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("sea:try:"))
async def callback_shot(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    _, _, session_id_text, row_text, col_text = callback.data.split(":")
    session_id = int(session_id_text)
    row = int(row_text)
    col = int(col_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None or session.status != SessionStatus.active:
        await callback.answer()
        return

    if session.mode == SessionMode.duel_private:
        await _handle_duel_shot(callback, session, user, lang, row, col)
        return

    await callback.answer()
    if session.created_by_user_id != user.id:
        return

    state = dict(session.state)
    menu_msg_id = state.get("menu_message_id")
    if state["current_turn"] != "user" or state["bot_cover"][row][col]:
        return

    user_result = game.make_move(state, row, col, is_user=True)
    state = user_result["game_state"]

    if user_result["game_over"]:
        await finish_session(session.id, state, winner_user_id=user.id)
        await record_game_result(user.id, game.code, "win")
        await redraw(callback.message, session.id, lang, state, is_game_over=True, is_win=True)
        if menu_msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
            except Exception:
                pass
        await open_battleship_menu(callback.message, user, lang)
        return

    await redraw(callback.message, session.id, lang, state)
    if state["current_turn"] == "bot":
        state, outcome = await run_computer_turns(callback.message, session.id, lang, state)
        if outcome == "loss":
            await finish_session(session.id, state, winner_user_id=None)
            await record_game_result(user.id, game.code, "loss")
            if menu_msg_id:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, menu_msg_id)
                except Exception:
                    pass
            await open_battleship_menu(callback.message, user, lang)
            return

    await update_session_state(session.id, state, current_turn_user_id=user.id if state["status"] == "active" else None)

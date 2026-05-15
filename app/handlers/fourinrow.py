import asyncio

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.models import SessionMode, SessionStatus
from app.games.fourinrow import game
from app.games.fourinrow.keyboards import SYMBOLS, board_keyboard, drop_keyboard
from app.handlers.filters import GameCallbackFilter
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard, group_duel_keyboard
from app.keyboards.games import game_menu_keyboard
from app.keyboards.main_menu import main_menu_keyboard
from app.services.duels import (
    broadcast_private_duel_update,
    build_duel_invite_text,
    get_duel_highlight,
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
    format_game_stats_text,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import format_player_name, get_user_by_id, update_user_settings, upsert_user


router = Router()


def four_menu_keyboard(lang: dict[str, str], chat_type=None):
    return game_menu_keyboard(
        lang,
        game_code=game.code,
        extra_duel_key="duel",
        extra_group_key="group",
        chat_type=chat_type,
    )


def get_duel_player_ids(state: dict) -> list[int | None]:
    return [state.get("player_red_id"), state.get("player_yellow_id")]


def get_player_sign(state: dict, user_id: int) -> int:
    return 1 if state.get("player_red_id") == user_id else 2


def render_group_status_text(
    lang: dict[str, str],
    state: dict,
    player_names: dict[int, str],
) -> str:
    if state["status"] == "finished":
        if state.get("result") == "draw":
            return lang["game-draw"]
        winner_id = state.get("winner_user_id")
        winner_symbol = SYMBOLS[1] if winner_id == state.get("player_red_id") else SYMBOLS[2]
        winner_name = player_names.get(winner_id, str(winner_id or ""))
        return f"{lang['group-winner']} {winner_symbol} {winner_name}"

    current_turn_user_id = state.get("current_turn_user_id")
    current_symbol = SYMBOLS[1] if current_turn_user_id == state.get("player_red_id") else SYMBOLS[2]
    current_name = player_names.get(current_turn_user_id, str(current_turn_user_id or ""))
    return f"{lang['game-four']}\n\n{lang['group-turn']} {current_symbol} {current_name}"


def render_text(lang: dict[str, str], state: dict, viewer_user_id: int | None = None) -> str:
    if state.get("player_red_id") and state.get("player_yellow_id"):
        if state["status"] == "finished":
            result = state.get("result")
            if result == "draw":
                return lang["game-draw"]
            if viewer_user_id is not None and viewer_user_id == state.get("winner_user_id"):
                return lang["game-win"]
            return lang["game-lose"]
        current_sign = 1 if state.get("current_turn_user_id") == state.get("player_red_id") else 2
        turn_line = lang["turn-user"] if viewer_user_id == state.get("current_turn_user_id") else lang["turn-friend"]
        return f"{lang['game-four']}\n\n{SYMBOLS[current_sign]} {turn_line}"

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


def render_drop_text(lang: dict[str, str], sign: int, viewer_turn: str) -> str:
    if viewer_turn == "user":
        turn_line = lang["turn-user"]
    elif viewer_turn == "friend":
        turn_line = lang["turn-friend"]
    else:
        turn_line = lang["turn-comp"]
    return f"{lang['game-four']}\n\n{SYMBOLS[sign]} {turn_line}"


async def animate_drop(message: Message, session_id: int, board: list[list[int]], sign: int, row: int, col: int, lang: dict[str, str], is_user: bool) -> None:
    for now_row in range(row):
        await asyncio.sleep(0.2)
        try:
            await message.edit_text(
                render_drop_text(lang, sign, "user" if is_user else "comp"),
                reply_markup=drop_keyboard(session_id, board, sign, row, now_row, col),
            )
        except TelegramBadRequest:
            pass


async def animate_duel_drop(bot, session, sign: int, row: int, col: int) -> None:
    state = dict(session.state or {})
    player_ids = get_duel_player_ids(state)
    message_map = get_duel_message_map(state)
    for now_row in range(row):
        await asyncio.sleep(0.2)

        async def render_frame(user_id: int):
            user = await get_user_by_id(user_id)
            if user is None:
                raise ValueError("User not found")
            lang = get_language_pack(user.language_code)
            viewer_turn = "user" if user_id == session.current_turn_user_id else "friend"
            return (
                render_drop_text(lang, sign, viewer_turn),
                drop_keyboard(session.id, state["board"], sign, row, now_row, col),
            )

        await broadcast_private_duel_update(bot, player_ids, message_map, render_frame)


async def animate_group_drop(message: Message, session_id: int, board: list[list[int]], sign: int, row: int, col: int, lang: dict[str, str], player_names: dict[int, str], state: dict) -> None:
    for now_row in range(row):
        await asyncio.sleep(0.2)
        try:
            await message.edit_text(
                render_group_status_text(lang, state, player_names),
                reply_markup=drop_keyboard(session_id, board, sign, row, now_row, col),
            )
        except TelegramBadRequest:
            pass

    try:
        await message.edit_text(
            render_group_status_text(lang, state, player_names),
            reply_markup=drop_keyboard(session_id, board, sign, row, row, col),
        )
    except TelegramBadRequest:
        pass


async def render_duel_message_for_user(session, user_id: int) -> tuple[str, object]:
    user = await get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found")
    lang = get_language_pack(user.language_code)
    state = dict(session.state or {})
    if session.mode == SessionMode.group_match:
        player_names: dict[int, str] = {}
        for player_id in get_duel_player_ids(state):
            if player_id is None:
                continue
            player_names[player_id] = format_player_name(await get_user_by_id(player_id))
        text = render_group_status_text(lang, state, player_names)
        is_active = session.status == SessionStatus.active
    else:
        text = render_text(lang, state, viewer_user_id=user_id)
        is_active = session.status == SessionStatus.active and session.current_turn_user_id == user_id
    markup = board_keyboard(
        session.id,
        state["board"],
        is_active,
        get_duel_highlight(state),
    )
    return text, markup


async def sync_duel_messages(bot, session) -> None:
    state = dict(session.state or {})
    await broadcast_private_duel_update(
        bot,
        get_duel_player_ids(state),
        get_duel_message_map(state),
        lambda user_id: render_duel_message_for_user(session, user_id),
    )


async def send_four_menu_to_other_duel_players(
    bot,
    state: dict,
    excluded_user_id: int,
    current_chat_id: int,
    current_chat_type,
) -> None:
    message_map = get_duel_message_map(state)
    for player_id in get_duel_player_ids(state):
        if player_id is None or player_id == excluded_user_id:
            continue
        message_meta = message_map.get(str(player_id))
        if not message_meta:
            continue
        user = await get_user_by_id(player_id)
        if user is None:
            continue
        lang = get_language_pack(user.language_code)
        chat_type = current_chat_type if message_meta["chat_id"] == current_chat_id else ChatType.PRIVATE
        try:
            await bot.send_message(
                chat_id=message_meta["chat_id"],
                text=lang["game-four"],
                reply_markup=four_menu_keyboard(lang, chat_type=chat_type),
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
            get_duel_highlight(session.state),
        ),
    )


async def start_four_duel(message: Message, user, lang: dict[str, str]) -> None:
    state = {"status": "pending", "message_ids": {}}
    session = await create_private_duel_invite(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    invite_message = await message.answer(
        build_duel_invite_text(lang, session.join_code or ""),
        reply_markup=duel_invite_keyboard(lang, session.join_code or ""),
    )
    set_duel_message_ref(state, user.id, invite_message)
    await update_session_state(session.id, state, None)


async def start_four_group(message: Message, user, lang: dict[str, str]) -> None:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.answer(
            lang["group-only"],
            reply_markup=four_menu_keyboard(lang, chat_type=message.chat.type),
        )
        return

    state = {
        "status": "pending",
    }
    session = await create_group_match_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    await message.answer(
        lang["group-wait"],
        reply_markup=group_duel_keyboard(lang, f"fir:group_join:{session.id}"),
    )
    await update_session_state(session.id, state, None)


async def join_private_duel(message: Message, user, lang: dict[str, str], session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(
            lang["duel-self"],
            reply_markup=four_menu_keyboard(lang, chat_type=message.chat.type),
        )
        return

    await update_user_settings(user.id, {"current_game": game.code})

    duel_state = game.new_duel_state(
        host_user_id=session.created_by_user_id,
        guest_user_id=user.id,
    )
    duel_state["message_ids"] = get_duel_message_map(state)

    session = await activate_private_duel_session(
        session.id,
        guest_user_id=user.id,
        state=duel_state,
        current_turn_user_id=duel_state["current_turn_user_id"],
    )
    if session is None:
        await message.answer(
            lang["duel-missing"],
            reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
        )
        return

    await message.answer(
        lang["duel-join-ok"],
        reply_markup=four_menu_keyboard(lang, chat_type=message.chat.type),
    )
    guest_message = await message.answer(
        render_text(lang, duel_state, viewer_user_id=user.id),
        reply_markup=board_keyboard(
            session.id,
            duel_state["board"],
            session.current_turn_user_id == user.id,
            [],
        ),
    )
    set_duel_message_ref(duel_state, user.id, guest_message)
    session = await update_session_state(session.id, duel_state, duel_state["current_turn_user_id"])
    if session is not None:
        await sync_duel_messages(message.bot, session)


async def open_four_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(
        lang["game-four"],
        reply_markup=four_menu_keyboard(lang, chat_type=message.chat.type),
    )


@router.message(Command("fourinrow"))
async def cmd_four_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_four_menu(message, user, lang)


@router.callback_query(F.data == "game:four")
async def open_four_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_four_menu(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("bot", game.code))
async def menu_new_game(callback: CallbackQuery, user, lang) -> None:
    await start_four_game(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("duel", game.code))
async def menu_new_duel(callback: CallbackQuery, user, lang) -> None:
    await start_four_duel(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("group", game.code))
async def menu_new_group(callback: CallbackQuery, user, lang) -> None:
    await start_four_group(callback.message, user, lang)
    await callback.answer()


@router.callback_query(GameCallbackFilter("stat", game.code))
async def menu_stats(callback: CallbackQuery, user, lang) -> None:
    text = await get_four_stats_text(user.id, lang)
    await callback.message.answer(text, 
        reply_markup=four_menu_keyboard(lang, chat_type=callback.message.chat.type),
        )
    await callback.answer()


@router.callback_query(GameCallbackFilter("help", game.code))
async def menu_help(callback: CallbackQuery, user, lang) -> None:
    await callback.message.answer(lang["help-four"], 
        reply_markup=four_menu_keyboard(lang, chat_type=callback.message.chat.type),
        )
    await callback.answer()


@router.callback_query(F.data == "fir:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("fir:group_join:"))
async def callback_four_group_join(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    session_id = int(callback.data.split(":")[2])
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

    player_ids = {player.user_id for player in session.players}
    if user.id in player_ids:
        await callback.answer(lang["group-already-joined"], show_alert=True)
        return
    if len(player_ids) >= 2:
        await callback.answer(lang["duel-full"], show_alert=True)
        return

    original_state = dict(session.state or {})
    duel_state = game.new_duel_state(
        host_user_id=session.created_by_user_id,
        guest_user_id=user.id,
    )
    session = await activate_group_match_session(
        session.id,
        user.id,
        duel_state,
        duel_state["current_turn_user_id"],
    )
    if session is None:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return

    player_names = {
        player_id: format_player_name(await get_user_by_id(player_id))
        for player_id in get_duel_player_ids(duel_state)
        if player_id is not None
    }
    await callback.message.edit_text(
        render_group_status_text(lang, duel_state, player_names),
        reply_markup=board_keyboard(
            session.id,
            duel_state["board"],
            True,
            [],
        ),
    )
    await callback.answer(lang["duel-join-ok"])


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
    if session is None:
        return

    state = dict(session.state or {})
    if session.mode == SessionMode.group_match:
        player_ids = {player.user_id for player in session.players}
        if user.id not in player_ids:
            return
        if session.status != SessionStatus.active:
            return
        if session.current_turn_user_id != user.id:
            return
        if state["board"][0][col] != 0:
            return

        player_sign = get_player_sign(state, user.id)
        duel_result = game.process_turn(state, player_sign, col, True)
        state = duel_result["game_state"]
        move_row, move_col = state["last_move"]
        state["highlight_line"] = duel_result["line"]
        player_names = {
            state["player_red_id"]: format_player_name(await get_user_by_id(state["player_red_id"])),
            state["player_yellow_id"]: format_player_name(await get_user_by_id(state["player_yellow_id"])),
        }

        if duel_result["state"] in {"win", "draw"}:
            state["result"] = duel_result["state"]
            state["winner_user_id"] = user.id if duel_result["state"] == "win" else None
            state["current_turn_user_id"] = None
            await finish_session(session.id, state, winner_user_id=state["winner_user_id"])
            other_user_id = state["player_yellow_id"] if state["player_red_id"] == user.id else state["player_red_id"]
            if duel_result["state"] == "draw":
                await record_game_result(user.id, game.code, "draw")
                await record_game_result(other_user_id, game.code, "draw")
            else:
                await record_game_result(user.id, game.code, "win")
                await record_game_result(other_user_id, game.code, "loss")
            await callback.message.edit_text(
                render_group_status_text(lang, state, player_names),
                reply_markup=board_keyboard(session.id, state["board"], False, duel_result["line"]),
            )
            await open_four_menu(callback.message, user, lang)
            await send_four_menu_to_other_duel_players(
                callback.bot,
                state,
                excluded_user_id=user.id,
                current_chat_id=callback.message.chat.id,
                current_chat_type=callback.message.chat.type,
            )
            return

        next_user_id = state["player_yellow_id"] if state["player_red_id"] == user.id else state["player_red_id"]
        state["current_turn_user_id"] = next_user_id
        await animate_group_drop(callback.message, session.id, state["board"], player_sign, move_row, move_col, lang, player_names, state)
        updated_session = await update_session_state(session.id, state, next_user_id)
        if updated_session is not None:
            await callback.message.edit_text(
                render_group_status_text(lang, state, player_names),
                reply_markup=board_keyboard(session.id, state["board"], True, duel_result["line"]),
            )
        return

    if session.mode == SessionMode.duel_private:
        player_ids = set(get_duel_player_ids(state))
        if user.id not in player_ids:
            return
        if session.status != SessionStatus.active:
            return
        if session.current_turn_user_id != user.id:
            return
        if state["board"][0][col] != 0:
            return

        player_sign = get_player_sign(state, user.id)
        duel_result = game.process_turn(state, player_sign, col, True)
        state = duel_result["game_state"]
        move_row, move_col = state["last_move"]
        state["highlight_line"] = duel_result["line"]
        await animate_duel_drop(callback.bot, session, player_sign, move_row, move_col)

        if duel_result["state"] in {"win", "draw"}:
            state["result"] = duel_result["state"]
            state["winner_user_id"] = user.id if duel_result["state"] == "win" else None
            state["current_turn_user_id"] = None
            await finish_session(session.id, state, winner_user_id=state["winner_user_id"])
            other_user_id = state["player_yellow_id"] if state["player_red_id"] == user.id else state["player_red_id"]
            if duel_result["state"] == "draw":
                await record_game_result(user.id, game.code, "draw")
                await record_game_result(other_user_id, game.code, "draw")
            else:
                await record_game_result(user.id, game.code, "win")
                await record_game_result(other_user_id, game.code, "loss")
            refreshed_session = await get_session_by_id(session.id)
            if refreshed_session is not None:
                await sync_duel_messages(callback.bot, refreshed_session)
            await open_four_menu(callback.message, user, lang)
            await send_four_menu_to_other_duel_players(
                callback.bot,
                state,
                excluded_user_id=user.id,
                current_chat_id=callback.message.chat.id,
                current_chat_type=callback.message.chat.type,
            )
            return

        next_user_id = state["player_yellow_id"] if state["player_red_id"] == user.id else state["player_red_id"]
        state["current_turn_user_id"] = next_user_id
        updated_session = await update_session_state(session.id, state, next_user_id)
        if updated_session is not None:
            await sync_duel_messages(callback.bot, updated_session)
        return

    if session.created_by_user_id != user.id or session.status != SessionStatus.active:
        return
    state = dict(session.state)
    user_result = game.process_turn(state, state["user_sign"], col, True)
    state = user_result["game_state"]
    user_row, user_col = state["last_move"]
    state["highlight_line"] = user_result["line"]
    await animate_drop(callback.message, session.id, state["board"], state["user_sign"], user_row, user_col, lang, True)
    if user_result["state"] in {"win", "draw"}:
        state["result"] = user_result["state"]
        await finish_session(session.id, state, winner_user_id=user.id if user_result["state"] == "win" else None)
        await record_game_result(user.id, game.code, "win" if user_result["state"] == "win" else "draw")
        await callback.message.edit_text(
            render_text(lang, state),
            reply_markup=board_keyboard(session.id, state["board"], False, user_result["line"]),
        )
        await open_four_menu(callback.message, user, lang)
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
    state["highlight_line"] = bot_result["line"]
    await animate_drop(callback.message, session.id, state["board"], state["bot_sign"], bot_row, bot_col, lang, False)
    if bot_result["state"] in {"loss", "draw"}:
        state["result"] = bot_result["state"]
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, "loss" if bot_result["state"] == "loss" else "draw")
        await callback.message.edit_text(
            render_text(lang, state),
            reply_markup=board_keyboard(session.id, state["board"], False, bot_result["line"]),
        )
        await open_four_menu(callback.message, user, lang)
        return

    state["current_turn"] = "user"
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_text(lang, state),
        reply_markup=board_keyboard(session.id, state["board"], True, bot_result["line"]),
    )


async def get_four_stats_text(user_id: int, lang: dict[str, str]) -> str:
    stat = await get_game_stat(user_id, game.code)
    return format_game_stats_text(stat, lang, ["played", "wins", "losses", "draws"])

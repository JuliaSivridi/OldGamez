from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from app.filters.current_game import CurrentGameFilter
from app.games.tictactoe import game
from app.games.tictactoe.keyboards import board_keyboard, size_keyboard
from app.i18n.translator import get_language_pack
from app.keyboards.duels import duel_invite_keyboard
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
    activate_private_duel_session,
    create_private_duel_invite,
    create_solo_session,
    finish_session,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import get_user_by_id, update_user_settings, upsert_user


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


def tictactoe_menu_keyboard(lang: dict[str, str]):
    return game_menu_keyboard(
        lang,
        extra_setting_key="menu-size",
        extra_action_key="menu-friend",
    )


def get_duel_player_ids(state: dict) -> list[int | None]:
    return [state.get("player_x_id"), state.get("player_o_id")]


def get_player_symbol(state: dict, user_id: int) -> str:
    return "x" if state.get("player_x_id") == user_id else "o"


def render_status_text(state: dict, lang: dict[str, str], viewer_user_id: int | None = None) -> str:
    board_size = state["board_size"]
    win_length = state["win_length"]

    if state.get("player_x_id") and state.get("player_o_id"):
        x_symbol = "❌"
        o_symbol = "⭕️"
        current_turn_user_id = state.get("current_turn_user_id")
        current_symbol = x_symbol if current_turn_user_id == state.get("player_x_id") else o_symbol

        if state["status"] == "finished":
            if state.get("result") == "draw":
                return lang["game-draw"]
            if viewer_user_id is not None and viewer_user_id == state.get("winner_user_id"):
                return lang["game-win"]
            return lang["game-lose"]

        turn_line = lang["turn-user"] if viewer_user_id == current_turn_user_id else lang["turn-friend"]
        return (
            f"{lang['game-xo']}{board_size}x{board_size}"
            f"{lang['xo-win-need']}{win_length}\n\n"
            f"{current_symbol} {turn_line}"
        )

    user_symbol = "❌" if state["user_symbol"] == "x" else "⭕️"
    bot_symbol = "⭕️" if state["user_symbol"] == "x" else "❌"

    if state["status"] == "finished":
        result = state.get("result")
        if result == "win":
            return lang["game-win"]
        if result == "loss":
            return lang["game-lose"]
        return lang["game-draw"]

    turn_line = lang["turn-user"] if state["current_turn"] == "user" else lang["turn-comp"]
    current_symbol = user_symbol if state["current_turn"] == "user" else bot_symbol
    return (
        f"{lang['game-xo']}{board_size}x{board_size}"
        f"{lang['xo-win-need']}{win_length}\n\n"
        f"{current_symbol} {turn_line}"
    )


async def render_duel_message_for_user(session, user_id: int) -> tuple[str, object]:
    user = await get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found")
    lang = get_language_pack(user.language_code)
    state = dict(session.state or {})
    is_active = session.status.value == "active" and session.current_turn_user_id == user_id
    text = render_status_text(state, lang, viewer_user_id=user_id)
    markup = board_keyboard(
        session_id=session.id,
        board=state["board"],
        board_size=state["board_size"],
        is_active=is_active,
        highlight=get_duel_highlight(state),
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


async def start_tictactoe_game(message: Message, user, lang: dict[str, str], size: int) -> None:
    state = game.new_game_state(board_size=size)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=message.chat.id,
        game_code=game.code,
        initial_state=state,
    )
    state = session.state
    await message.answer(
        render_status_text(state, lang),
        reply_markup=board_keyboard(
            session_id=session.id,
            board=state["board"],
            board_size=state["board_size"],
            is_active=state["current_turn"] == "user",
            highlight=get_duel_highlight(state),
        ),
    )


async def start_tictactoe_duel(message: Message, user, lang: dict[str, str], size: int) -> None:
    state = {
        "board_size": size,
        "status": "pending",
        "message_ids": {},
        "win_length": game.get_win_length(size),
    }
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


async def open_tictactoe_menu(message: Message, user, lang) -> None:
    await update_user_settings(user.id, {"current_game": game.code})
    await message.answer(lang["game-xo"], reply_markup=tictactoe_menu_keyboard(lang))


async def join_private_duel(message: Message, user, lang: dict[str, str], session) -> None:
    state = dict(session.state or {})
    if session.created_by_user_id == user.id:
        await message.answer(lang["duel-self"], reply_markup=tictactoe_menu_keyboard(lang))
        return

    await update_user_settings(user.id, {"current_game": game.code})

    duel_state = game.new_duel_state(
        board_size=int(state.get("board_size", 3)),
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
        await message.answer(lang["duel-missing"], reply_markup=main_menu_keyboard(lang))
        return

    await message.answer(lang["duel-join-ok"], reply_markup=tictactoe_menu_keyboard(lang))
    guest_message = await message.answer(
        render_status_text(duel_state, lang, viewer_user_id=user.id),
        reply_markup=board_keyboard(
            session_id=session.id,
            board=duel_state["board"],
            board_size=duel_state["board_size"],
            is_active=session.current_turn_user_id == user.id,
            highlight=[],
        ),
    )
    set_duel_message_ref(duel_state, user.id, guest_message)
    session = await update_session_state(session.id, duel_state, duel_state["current_turn_user_id"])
    if session is not None:
        await sync_duel_messages(message.bot, session)


@router.message(Command("tictactoe"))
@router.message(Command("xo"))
async def cmd_tictactoe_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await open_tictactoe_menu(message, user, lang)


@router.message(MenuTextFilter("menu-xo"))
async def cmd_tictactoe_menu(message: Message, user, lang) -> None:
    await open_tictactoe_menu(message, user, lang)


@router.callback_query(F.data == "game:xo")
async def open_tictactoe_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await open_tictactoe_menu(callback.message, user, lang)
    await callback.answer()


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-bot"))
async def menu_new_game(message: Message, user, lang) -> None:
    size = int((user.settings or {}).get("tictactoe_size", 3))
    await start_tictactoe_game(message, user, lang, size)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-friend"))
async def menu_new_duel(message: Message, user, lang) -> None:
    size = int((user.settings or {}).get("tictactoe_size", 3))
    await start_tictactoe_duel(message, user, lang, size)


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-size"))
async def menu_tictactoe_size(message: Message, user, lang) -> None:
    await message.answer(lang["chus-size"], reply_markup=size_keyboard(lang))


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-hlp"))
async def menu_help(message: Message, user, lang) -> None:
    await message.answer(lang["help-xo"], parse_mode="Markdown")


@router.message(CurrentGameFilter(game.code), MenuTextFilter("menu-stat"))
async def menu_stats(message: Message, **kwargs) -> None:
    await cmd_tictactoe_stats(message)


@router.callback_query(F.data.startswith("ttt:size:"))
async def callback_tictactoe_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await update_user_settings(user.id, {"tictactoe_size": size, "current_game": game.code})
    await callback.message.answer(
        lang["size-saved"],
        reply_markup=tictactoe_menu_keyboard(lang),
    )


@router.callback_query(F.data == "ttt:noop")
async def callback_tictactoe_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("ttt:move:"))
async def callback_tictactoe_move(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    _, _, session_id_text, position_text = callback.data.split(":")
    session_id = int(session_id_text)
    position = int(position_text)

    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    session = await get_session_by_id(session_id)
    if session is None:
        await callback.answer(lang["duel-missing"], show_alert=True)
        return

    state = dict(session.state or {})
    if session.mode.value == "duel_private":
        player_ids = set(get_duel_player_ids(state))
        if user.id not in player_ids:
            await callback.answer(lang["xo-not-yours"], show_alert=True)
            return
        if session.status.value != "active":
            await callback.answer(lang["xo-already-finished"], show_alert=True)
            return
        if session.current_turn_user_id != user.id:
            await callback.answer(lang["xo-not-your-turn"], show_alert=True)
            return
        if state["board"][position] != ".":
            await callback.answer(lang["xo-cell-busy"], show_alert=True)
            return

        player_symbol = get_player_symbol(state, user.id)
        duel_turn = game.process_turn(
            board=state["board"],
            board_size=state["board_size"],
            sign=player_symbol,
            position=position,
            is_user=True,
        )
        state["board"] = duel_turn.board
        state["last_move"] = duel_turn.highlight[0] if duel_turn.highlight else None
        state["highlight_line"] = duel_turn.highlight

        if duel_turn.game_over:
            state["status"] = "finished"
            state["result"] = duel_turn.state
            state["winner_user_id"] = user.id if duel_turn.state == "win" else None
            state["current_turn_user_id"] = None
            await finish_session(
                session.id,
                state,
                winner_user_id=state["winner_user_id"],
            )
            other_user_id = state["player_o_id"] if state["player_x_id"] == user.id else state["player_x_id"]
            if duel_turn.state == "draw":
                await record_game_result(user.id, game.code, "draw")
                await record_game_result(other_user_id, game.code, "draw")
            else:
                await record_game_result(user.id, game.code, "win")
                await record_game_result(other_user_id, game.code, "loss")
            refreshed_session = await get_session_by_id(session.id)
            if refreshed_session is not None:
                await sync_duel_messages(callback.bot, refreshed_session)
            await callback.answer()
            return

        next_user_id = state["player_o_id"] if state["player_x_id"] == user.id else state["player_x_id"]
        state["current_turn_user_id"] = next_user_id
        updated_session = await update_session_state(session.id, state, next_user_id)
        if updated_session is not None:
            await sync_duel_messages(callback.bot, updated_session)
        await callback.answer()
        return

    if session.created_by_user_id != user.id:
        await callback.answer(lang["xo-not-yours"], show_alert=True)
        return
    if session.status.value != "active":
        await callback.answer(lang["xo-already-finished"], show_alert=True)
        return
    if state["current_turn"] != "user":
        await callback.answer(lang["xo-not-your-turn"], show_alert=True)
        return
    if state["board"][position] != ".":
        await callback.answer(lang["xo-cell-busy"], show_alert=True)
        return

    user_turn = game.process_turn(
        board=state["board"],
        board_size=state["board_size"],
        sign=state["user_symbol"],
        position=position,
        is_user=True,
    )
    state["board"] = user_turn.board
    state["last_move"] = user_turn.highlight[0] if user_turn.highlight else None
    state["highlight_line"] = user_turn.highlight

    if user_turn.game_over:
        state["status"] = "finished"
        state["result"] = user_turn.state
        await finish_session(session.id, state, winner_user_id=user.id if user_turn.state == "win" else None)
        await record_game_result(user.id, game.code, user_turn.state or "draw")
        await callback.message.edit_text(
            render_status_text(state, lang),
            reply_markup=board_keyboard(
                session_id=session.id,
                board=state["board"],
                board_size=state["board_size"],
                is_active=False,
                highlight=user_turn.highlight,
            ),
        )
        await callback.answer()
        return

    state["current_turn"] = "bot"

    bot_position = game.get_smart_move(
        board=state["board"],
        board_size=state["board_size"],
        bot_sign=state["bot_symbol"],
        user_sign=state["user_symbol"],
    )
    bot_turn = game.process_turn(
        board=state["board"],
        board_size=state["board_size"],
        sign=state["bot_symbol"],
        position=bot_position,
        is_user=False,
    )
    state["board"] = bot_turn.board
    state["last_move"] = bot_turn.highlight[0] if bot_turn.highlight else None
    state["highlight_line"] = bot_turn.highlight

    if bot_turn.game_over:
        state["status"] = "finished"
        state["result"] = bot_turn.state
        await finish_session(session.id, state, winner_user_id=None)
        await record_game_result(user.id, game.code, bot_turn.state or "draw")
        await callback.message.edit_text(
            render_status_text(state, lang),
            reply_markup=board_keyboard(
                session_id=session.id,
                board=state["board"],
                board_size=state["board_size"],
                is_active=False,
                highlight=bot_turn.highlight,
            ),
        )
        await callback.answer()
        return

    state["current_turn"] = "user"
    await update_session_state(session.id, state, current_turn_user_id=user.id)
    await callback.message.edit_text(
        render_status_text(state, lang),
        reply_markup=board_keyboard(
            session_id=session.id,
            board=state["board"],
            board_size=state["board_size"],
            is_active=True,
            highlight=bot_turn.highlight,
        ),
    )
    await callback.answer()


@router.message(Command("tictactoe_stats"))
async def cmd_tictactoe_stats(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        await message.answer(
            lang["stat-ttl"]
            + f"`{lang['stat-all']}{str(0).rjust(20 - len(lang['stat-all']))}`"
            + f"`{lang['stat-win']}{str(0).rjust(20 - len(lang['stat-win']))}`"
            + f"`{lang['stat-lose']}{str(0).rjust(20 - len(lang['stat-lose']))}`"
            + f"`{lang['stat-draw']}{str(0).rjust(21 - len(lang['stat-draw']))}`",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        lang["stat-ttl"]
        + f"`{lang['stat-all']}{str(stat.played).rjust(20 - len(lang['stat-all']))}`"
        + f"`{lang['stat-win']}{str(stat.wins).rjust(20 - len(lang['stat-win']))}`"
        + f"`{lang['stat-lose']}{str(stat.losses).rjust(20 - len(lang['stat-lose']))}`"
        + f"`{lang['stat-draw']}{str(stat.draws).rjust(21 - len(lang['stat-draw']))}`",
        parse_mode="Markdown",
    )

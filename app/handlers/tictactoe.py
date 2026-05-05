from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.games.tictactoe import game
from app.games.tictactoe.keyboards import board_keyboard, size_keyboard
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

router = Router()


def render_status_text(state: dict, lang: dict[str, str]) -> str:
    board_size = state["board_size"]
    win_length = state["win_length"]
    user_symbol = "❌" if state["user_symbol"] == "x" else "⭕"
    bot_symbol = "⭕" if state["user_symbol"] == "x" else "❌"

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


@router.message(Command("tictactoe"))
@router.message(Command("xo"))
async def cmd_tictactoe(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    await update_user_settings(user.id, {"current_game": game.code})
    lang = get_language_pack(user.language_code)
    preferred_size = int((user.settings or {}).get("tictactoe_size", 3))
    await message.answer(
        lang["menu-xo"],
        reply_markup=game_menu_keyboard(lang, has_size=True),
    )


@router.message(F.text.in_({"❌⭕️ TicTacToe", "❌⭕️ Крестики-нолики"}))
async def choose_tictactoe_from_menu(message: Message) -> None:
    await cmd_tictactoe(message)


@router.message(F.text.in_({"🆕 New game", "🆕 Новая игра"}))
async def menu_new_game(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    current_game = get_user_setting(user, "current_game")
    lang = get_language_pack(user.language_code)
    if current_game != game.code:
        await message.answer(lang["bot-choose-game-first"])
        return

    await message.answer(lang["chus-size"], reply_markup=size_keyboard(lang))


@router.message(F.text.in_({"🔢 Size", "🔢 Размер"}))
async def menu_tictactoe_size(message: Message) -> None:
    await menu_new_game(message)


@router.message(F.text.in_({"ℹ️ Help", "ℹ️ Помощь"}))
async def menu_tictactoe_help(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    current_game = get_user_setting(user, "current_game")
    lang = get_language_pack(user.language_code)
    if current_game != game.code:
        await message.answer(lang["bot-choose-game-first"])
        return

    await message.answer(lang["help-xo"], parse_mode="Markdown")


@router.message(F.text.in_({"📊 Statistics", "📊 Статистика"}))
async def menu_tictactoe_stats_from_context(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    current_game = get_user_setting(user, "current_game")
    if current_game != game.code:
        return
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

    state = game.new_game_state(board_size=size)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=callback.message.chat.id,
        game_code=game.code,
        initial_state=state,
    )

    state = session.state
    await callback.message.answer(
        render_status_text(state, lang),
        reply_markup=board_keyboard(
            session_id=session.id,
            board=state["board"],
            board_size=state["board_size"],
            is_active=state["current_turn"] == "user",
            highlight=[state["last_move"]] if state.get("last_move") else [],
        ),
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
    if session is None or session.created_by_user_id != user.id:
        await callback.answer(lang["ttt-not-yours"], show_alert=True)
        return
    if session.status.value != "active":
        await callback.answer(lang["ttt-already-finished"], show_alert=True)
        return

    state = dict(session.state)
    if state["current_turn"] != "user":
        await callback.answer(lang["ttt-not-your-turn"], show_alert=True)
        return
    if state["board"][position] != ".":
        await callback.answer(lang["ttt-cell-busy"], show_alert=True)
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

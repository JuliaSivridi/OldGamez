from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.games.tictactoe import game
from app.games.tictactoe.keyboards import board_keyboard, size_keyboard
from app.services.sessions import (
    create_solo_session,
    finish_session,
    get_active_solo_session,
    get_game_stat,
    get_session_by_id,
    record_game_result,
    update_session_state,
)
from app.services.users import update_user_settings, upsert_user

router = Router()


def render_status_text(state: dict) -> str:
    board_size = state["board_size"]
    win_length = state["win_length"]
    user_symbol = state["user_symbol"].upper()

    if state["status"] == "finished":
        result = state.get("result")
        if result == "win":
            return "Ты победила!\n\nИгра завершена."
        if result == "loss":
            return "Бот победил.\n\nИгра завершена."
        return "Ничья.\n\nИгра завершена."

    turn_line = "Твой ход." if state["current_turn"] == "user" else "Ход бота."
    return (
        f"Tic-Tac-Toe {board_size}x{board_size}\n"
        f"Для победы нужно собрать {win_length}.\n\n"
        f"Ты играешь за {user_symbol}.\n"
        f"{turn_line}"
    )


@router.message(Command("tictactoe"))
@router.message(Command("xo"))
async def cmd_tictactoe(message: Message) -> None:
    if message.from_user is None:
        return

    user = await upsert_user(message.from_user)
    preferred_size = int((user.settings or {}).get("tictactoe_size", 3))
    await message.answer(
        "Выбирай размер поля для новой игры.",
        reply_markup=size_keyboard(),
    )
    if preferred_size != 3:
        await message.answer(
            f"Сейчас у тебя сохранен размер по умолчанию: {preferred_size}x{preferred_size}."
        )


@router.callback_query(F.data.startswith("ttt:size:"))
async def callback_tictactoe_size(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    await callback.answer()
    size = int(callback.data.split(":")[2])
    user = await upsert_user(callback.from_user)
    await update_user_settings(user.id, {"tictactoe_size": size})

    state = game.new_game_state(board_size=size)
    session = await create_solo_session(
        user_id=user.id,
        telegram_chat_id=callback.message.chat.id,
        game_code=game.code,
        initial_state=state,
    )

    state = session.state
    await callback.message.answer(
        render_status_text(state),
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
    session = await get_session_by_id(session_id)
    if session is None or session.created_by_user_id != user.id:
        await callback.answer("Эта игра тебе не принадлежит.", show_alert=True)
        return
    if session.status.value != "active":
        await callback.answer("Эта игра уже завершена.", show_alert=True)
        return

    state = dict(session.state)
    if state["current_turn"] != "user":
        await callback.answer("Сейчас не твой ход.", show_alert=True)
        return
    if state["board"][position] != ".":
        await callback.answer("Эта клетка уже занята.", show_alert=True)
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
            render_status_text(state),
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
            render_status_text(state),
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
        render_status_text(state),
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
    stat = await get_game_stat(user.id, game.code)
    if stat is None:
        await message.answer("По крестикам-ноликам пока нет сыгранных партий.")
        return

    await message.answer(
        "Статистика Tic-Tac-Toe:\n"
        f"Сыграно: {stat.played}\n"
        f"Побед: {stat.wins}\n"
        f"Поражений: {stat.losses}\n"
        f"Ничьих: {stat.draws}"
    )


@router.message(F.text == "Крестики-нолики")
async def menu_tictactoe(message: Message) -> None:
    await cmd_tictactoe(message)

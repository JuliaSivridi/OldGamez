from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.tictactoe.game import EMPTY_CELL, SYMBOLS


def size_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for size in range(3, 9):
        builder.button(text=lang[str(size)], callback_data=f"ttt:size:{size}")
    builder.adjust(3)
    return builder.as_markup()


def board_keyboard(
    session_id: int,
    board: str,
    board_size: int,
    is_active: bool,
    highlight: list[list[int]] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    highlight_set = {
        (row, col) for row, col in (highlight or [])
    }

    for row in range(board_size):
        for col in range(board_size):
            idx = row * board_size + col
            cell = board[idx]
            cell_text = SYMBOLS[cell]
            if (row, col) in highlight_set and cell != EMPTY_CELL:
                cell_text = f"[{cell_text}]"

            if is_active and cell == EMPTY_CELL:
                callback = f"ttt:move:{session_id}:{idx}"
            else:
                callback = "ttt:noop"
            builder.button(text=cell_text, callback_data=callback)

    builder.adjust(*([board_size] * board_size))
    return builder.as_markup()

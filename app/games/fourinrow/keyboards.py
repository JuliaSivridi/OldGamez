from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


SYMBOLS = {
    0: "⚪",
    1: "🔴",
    2: "🟡",
}


def board_keyboard(session_id: int, board: list[list[int]], is_active: bool, highlight: list[list[int]] | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    highlighted = {(r, c) for r, c in (highlight or [])}
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            text = f"({SYMBOLS[cell]})" if (r, c) in highlighted else SYMBOLS[cell]
            callback = f"fir:col:{session_id}:{c}" if board[0][c] == 0 and is_active else "fir:noop"
            builder.button(text=text, callback_data=callback)
    builder.adjust(*([7] * 6))
    return builder.as_markup()


def drop_keyboard(session_id: int, board: list[list[int]], sign: int, end_row: int, now_row: int, col: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if r == now_row and c == col:
                text = SYMBOLS[sign]
            elif r == end_row and c == col:
                text = SYMBOLS[0]
            else:
                text = SYMBOLS[cell]
            builder.button(text=text, callback_data="fir:noop")
    builder.adjust(*([7] * 6))
    return builder.as_markup()

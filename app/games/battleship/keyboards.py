from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


SYMBOLS = {
    4: "☠️",
    3: "🔥",
    2: "🚢",
    1: "🌀",
    0: "🟦",
    -1: "⬜️",
}


def board_keyboard(session_id: int, cover: list[list[bool]], board: list[list[int]], is_active: bool, is_game_over: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    size = len(board)
    if is_game_over:
        cover = [[True for _ in range(size)] for _ in range(size)]

    for row in range(size):
        for col in range(size):
            is_open = cover[row][col]
            text = SYMBOLS[board[row][col]] if is_open else SYMBOLS[-1]
            callback = f"sea:try:{session_id}:{row}:{col}" if is_active and not is_open else "sea:noop"
            builder.button(text=text, callback_data=callback)

    builder.adjust(*([size] * size))
    return builder.as_markup()

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

ON = "🟨"
OFF = "⬛"


def size_keyboard(lang: dict[str, str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for size in (4, 5, 6):
        builder.button(text=lang[str(size)], callback_data=f"lto:size:{size}")
    builder.adjust(3)
    return builder.as_markup()


def board_keyboard(session_id: int, cells: list[bool], size: int, active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, lit in enumerate(cells):
        text = ON if lit else OFF
        callback_data = f"lto:press:{session_id}:{idx}" if active else "lto:noop"
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(*([size] * size))
    return builder.as_markup()

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

ON = "🟨"
OFF = "⬛"


def size_keyboard(lang: dict[str, str], back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for size in (4, 5, 6):
        builder.button(text=f"{lang[str(size)]}✖️{lang[str(size)]}", callback_data=f"lto:size:{size}")
    builder.button(text=lang["main-back"], callback_data=back_callback)
    builder.adjust(3, 1)
    return builder.as_markup()


def board_keyboard(
    session_id: int,
    cells: list[bool],
    size: int,
    active: bool,
    lang: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row_sizes = []

    if active and lang is not None:
        builder.button(text=lang["lto-solve"], callback_data=f"lto:solve:{session_id}")
        builder.button(text=lang["lto-give-up"], callback_data=f"lto:give_up:{session_id}")
        row_sizes.append(2)

    for idx, lit in enumerate(cells):
        text = ON if lit else OFF
        callback_data = f"lto:press:{session_id}:{idx}" if active else "lto:noop"
        builder.button(text=text, callback_data=callback_data)
    row_sizes.extend([size] * size)

    builder.adjust(*row_sizes)
    return builder.as_markup()

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def size_keyboard(lang: dict[str, str], back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for size in range(3, 9):
        builder.button(text=f"{lang[str(size)]}✖️{lang[str(size)]}", callback_data=f"npz:size:{size}")
    builder.button(text=lang["main-back"], callback_data=back_callback)
    builder.adjust(3, 3, 1)
    return builder.as_markup()


def tiles_keyboard(session_id: int, tiles: list[int], size: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    space_pos = tiles.index(0)

    for idx, tile in enumerate(tiles):
        text = "  " if tile == 0 else str(tile)
        callback_data = "npz:noop"
        if (
            (idx == space_pos - 1 and idx % size != size - 1)
            or (idx == space_pos + 1 and idx % size != 0)
            or idx == space_pos - size
            or idx == space_pos + size
        ):
            callback_data = f"npz:move:{session_id}:{idx}"
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(*([size] * size))
    return builder.as_markup()


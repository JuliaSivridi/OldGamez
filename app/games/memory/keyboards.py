from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

FACE_DOWN = "⬜"


def board_keyboard(session_id: int, state: dict, active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    cards = state["cards"]
    matched = state["matched"]
    flipped = state.get("flipped", [])
    revealing = state.get("revealing", False)
    rows = state["rows"]
    cols = state["cols"]

    flipped_set = set(flipped)

    for idx in range(len(cards)):
        if matched[idx]:
            text = cards[idx]
            cb = "mem:noop"
        elif idx in flipped_set:
            text = cards[idx]
            cb = "mem:noop"
        else:
            text = FACE_DOWN
            cb = f"mem:flip:{session_id}:{idx}" if (active and not revealing) else "mem:noop"
        builder.button(text=text, callback_data=cb)

    builder.adjust(*([cols] * rows))
    return builder.as_markup()


def size_keyboard(lang: dict, back_callback: str) -> InlineKeyboardMarkup:
    from app.games.memory.game import GRID_DIMS
    builder = InlineKeyboardBuilder()
    for size in range(3, 9):
        rows, cols = GRID_DIMS[size]
        builder.button(
            text=f"{lang[str(rows)]}✖️{lang[str(cols)]}",
            callback_data=f"mem:size:{size}",
        )
    builder.button(text=lang["main-back"], callback_data=back_callback, style=ButtonStyle.SUCCESS)
    builder.adjust(3, 3, 1)
    return builder.as_markup()

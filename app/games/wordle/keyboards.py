from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.i18n.languages import LANGUAGE_LETTERS

ROW_SIZE = 8


def game_keyboard(session_id: int, state: dict, active: bool, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    letters = LANGUAGE_LETTERS.get(state["lang"], LANGUAGE_LETTERS["en"])
    current = state["current"]
    size = state["size"]

    can_add = active and len(current) < size
    for letter in letters:
        cb = f"wrd:letter:{session_id}:{letter}" if can_add else "wrd:noop"
        builder.button(text=letter, callback_data=cb)

    full_rows = len(letters) // ROW_SIZE
    remainder = len(letters) % ROW_SIZE
    row_sizes = [ROW_SIZE] * full_rows + ([remainder] if remainder else [])

    has_input = len(current) > 0
    is_full = len(current) == size
    del_cb = f"wrd:back:{session_id}" if (active and has_input) else "wrd:noop"
    sub_cb = f"wrd:submit:{session_id}" if (active and is_full) else "wrd:noop"
    builder.button(text=lang["btn-delete"], callback_data=del_cb)
    builder.button(text=lang["btn-submit"], callback_data=sub_cb)
    row_sizes.append(2)

    builder.adjust(*row_sizes)
    return builder.as_markup()

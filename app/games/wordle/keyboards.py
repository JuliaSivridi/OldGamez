from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.i18n.languages import LANGUAGE_LETTERS

ROW_SIZE = 8


def game_keyboard(session_id: int, state: dict, active: bool, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    letters = LANGUAGE_LETTERS.get(state["lang"], LANGUAGE_LETTERS["en"])
    current = state["current"]

    present_letters = {
        letter
        for entry in state["history"]
        for letter, mark in zip(entry["guess"], entry["marks"])
        if mark != "grey"
    }
    grey_letters = {
        letter
        for entry in state["history"]
        for letter, mark in zip(entry["guess"], entry["marks"])
        if mark == "grey"
    } - present_letters

    can_add = active and None in current
    for letter in letters:
        is_grey = letter.upper() in grey_letters
        cb = f"wrd:letter:{session_id}:{letter}" if (can_add and not is_grey) else "wrd:noop"
        builder.button(text="*" if is_grey else letter, callback_data=cb)

    full_rows = len(letters) // ROW_SIZE
    remainder = len(letters) % ROW_SIZE
    row_sizes = [ROW_SIZE] * full_rows + ([remainder] if remainder else [])

    has_input = any(v is not None and i not in set(state.get("hint_positions", [])) for i, v in enumerate(current))
    is_full = active and None not in current
    has_hint = active and None in current

    del_cb = f"wrd:back:{session_id}" if (active and has_input) else "wrd:noop"
    hint_cb = f"wrd:hint:{session_id}" if has_hint else "wrd:noop"
    sub_cb = f"wrd:submit:{session_id}" if is_full else "wrd:noop"

    builder.button(text=lang["btn-delete"], callback_data=del_cb, style=ButtonStyle.DANGER)
    builder.button(text=lang["wrd-hint"], callback_data=hint_cb)
    builder.button(text=lang["btn-submit"], callback_data=sub_cb, style=ButtonStyle.SUCCESS)
    row_sizes.append(3)

    builder.adjust(*row_sizes)
    return builder.as_markup()

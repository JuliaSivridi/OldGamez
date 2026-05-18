from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def game_keyboard(session_id: int, state: dict, active: bool, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    current = state["current"]
    size = state["size"]

    for digit in range(10):
        already_chosen = digit in current
        can_press = active and len(current) < size and not already_chosen
        cb = f"bc:digit:{session_id}:{digit}" if can_press else "bc:noop"
        builder.button(text="*" if already_chosen else str(digit), callback_data=cb)
    builder.adjust(5, 5)

    has_input = len(current) > 0
    is_full = len(current) == size
    del_cb = f"bc:back:{session_id}" if (active and has_input) else "bc:noop"
    sub_cb = f"bc:submit:{session_id}" if (active and is_full) else "bc:noop"
    builder.button(text=lang["btn-delete"], callback_data=del_cb, style=ButtonStyle.DANGER)
    builder.button(text=lang["btn-submit"], callback_data=sub_cb, style=ButtonStyle.SUCCESS)
    builder.adjust(5, 5, 2)

    return builder.as_markup()



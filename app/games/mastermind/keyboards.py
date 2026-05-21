from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BLANK = "⬛"


def game_keyboard(session_id: int, state: dict, active: bool, lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    colors = state["colors"]
    current = state["current"]
    size = state["size"]

    for idx, color in enumerate(colors):
        can_press = active and len(current) < size
        cb = f"mm:color:{session_id}:{idx}" if can_press else "mm:noop"
        builder.button(text=color, callback_data=cb)
    builder.adjust(len(colors))

    has_input = len(current) > 0
    is_full = len(current) == size
    del_cb = f"mm:back:{session_id}" if (active and has_input) else "mm:noop"
    sub_cb = f"mm:submit:{session_id}" if (active and is_full) else "mm:noop"
    builder.button(text=lang["btn-delete"], callback_data=del_cb, style=ButtonStyle.DANGER)
    builder.button(text=lang["btn-submit"], callback_data=sub_cb, style=ButtonStyle.SUCCESS)
    builder.adjust(len(colors), 2)

    return builder.as_markup()


def cmplx_keyboard(lang: dict, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, value in (("cmplx-easy", "easy"), ("cmplx-norm", "norm"), ("cmplx-hard", "hard")):
        builder.button(text=lang[key], callback_data=f"mm:cmplx:{value}")
    builder.button(text=lang["main-back"], callback_data=back_callback, style=ButtonStyle.SUCCESS)
    builder.adjust(3, 1)
    return builder.as_markup()

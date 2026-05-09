from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def game_keyboard(session_id: int, lang: dict[str, str], is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["menu-more"], callback_data=f"bj:hit:{session_id}" if is_active else "bj:noop")
    builder.button(text=lang["menu-stop"], callback_data=f"bj:stand:{session_id}" if is_active else "bj:noop")
    builder.adjust(2)
    return builder.as_markup()

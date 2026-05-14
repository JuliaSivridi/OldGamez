from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if chat_type in ("group", "supergroup"):
        builder.button(text=lang["menu-group-games"], callback_data="menu:group-games")
    else:
        builder.button(text=lang["menu-games"], callback_data="menu:games")
    builder.button(text=lang["menu-lang"], callback_data="menu:lang")
    builder.adjust(2)
    return builder.as_markup()

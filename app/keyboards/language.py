from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def language_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 ru", callback_data="lang:ru")
    builder.button(text="🇫🇮 fi", callback_data="lang:fi")
    builder.button(text="🇬🇧 en", callback_data="lang:en")
    builder.adjust(3)
    return builder.as_markup()


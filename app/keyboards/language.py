from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.i18n.languages import LANGUAGE_CHOICES


def language_keyboard(lang: dict[str, str], chat_type=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, code in LANGUAGE_CHOICES.items():
        builder.button(text=label, callback_data=f"lang:{code}")
    builder.adjust(3)
    return builder.as_markup()


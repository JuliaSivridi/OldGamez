from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 ru"), KeyboardButton(text="🇬🇧 en")],
        ],
        resize_keyboard=True,
    )


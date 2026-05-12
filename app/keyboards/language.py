from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def language_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 ru"), KeyboardButton(text="🇫🇮 fi"), KeyboardButton(text="🇬🇧 en")],
            [KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


from aiogram.enums import ChatType
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def language_keyboard(lang: dict[str, str], chat_type: ChatType | str | None = None) -> ReplyKeyboardMarkup | None:
    if chat_type in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup"):
        return None

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 ru"), KeyboardButton(text="🇫🇮 fi"), KeyboardButton(text="🇬🇧 en")],
            [KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )


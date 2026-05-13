from aiogram.enums import ChatType
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(lang: dict[str, str], chat_type: ChatType | str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-games"]), KeyboardButton(text=lang["menu-lang"])],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

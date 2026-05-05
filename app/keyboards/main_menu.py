from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-xo"]), KeyboardButton(text=lang["menu-stat"])],
            [KeyboardButton(text=lang["menu-links"])],
        ],
        resize_keyboard=True,
    )

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-links"]), KeyboardButton(text=lang["menu-lang"])],
        ],
        resize_keyboard=True,
    )

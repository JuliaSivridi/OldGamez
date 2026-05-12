from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["menu-games"]), KeyboardButton(text=lang["menu-lang"])],
        ],
        resize_keyboard=True,
    )

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Крестики-нолики"), KeyboardButton(text="Статистика")],
            [KeyboardButton(text="Игры")],
        ],
        resize_keyboard=True,
    )

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def game_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["rps-stone"]), KeyboardButton(text=lang["rps-scissors"]), KeyboardButton(text=lang["rps-paper"])],
            [KeyboardButton(text=lang["menu-stat"]), KeyboardButton(text=lang["menu-help"]), KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )

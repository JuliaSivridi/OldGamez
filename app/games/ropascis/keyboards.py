from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def game_keyboard(lang: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lang["rsp-stone"]), KeyboardButton(text=lang["rsp-scissors"]), KeyboardButton(text=lang["rsp-paper"])],
            [KeyboardButton(text=lang["menu-stat"]), KeyboardButton(text=lang["menu-hlp"]), KeyboardButton(text=lang["main-back"])],
        ],
        resize_keyboard=True,
    )
